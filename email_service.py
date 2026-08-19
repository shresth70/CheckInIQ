import smtplib
import qrcode
import io
import threading
from PIL import Image, ImageDraw, ImageFont
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright
from card_templates import card_midnight
#--------------------- CONFIGURATION------------------
import os
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "xyz@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
#----------------------------------------------------------------

# ============================================================
# PERSISTENT SMTP CONNECTION
# ------------------------------------------------------------
# Before: every send_* function opened a brand-new SMTP connection,
# did the TLS handshake, and logged in from scratch. That handshake
# + login is the slow part (not the actual sending), so sending
# invites to N guests in a loop meant paying that cost N times in a
# row -> the whole request sits there waiting.
#
# Now: we log in ONCE and keep the connection open, reusing it for
# every email. If the connection ever drops (idle timeout, network
# hiccup) we transparently reconnect once and retry.
# ============================================================
class _SMTPClient:
    def __init__(self):
        self._server = None
        self._lock = threading.Lock()

    def _connect(self):
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        server.ehlo()
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        return server

    def send(self, msg, to_addr):
        """Thread-safe send using a shared, reused connection."""
        with self._lock:
            if self._server is None:
                self._server = self._connect()
            try:
                self._server.sendmail(EMAIL_ADDRESS, to_addr, msg.as_string())
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPException, OSError):
                # Connection died (idle timeout etc) - reconnect once and retry.
                try:
                    self._server.quit()
                except Exception:
                    pass
                self._server = self._connect()
                self._server.sendmail(EMAIL_ADDRESS, to_addr, msg.as_string())


_smtp_client = _SMTPClient()
def generate_qr_bytes(data: str) -> bytes :
    qr=qrcode.QRCode(box_size =9, border =3)
    qr.add_data(data)
    qr.make(fit= True)
    img = qr.make_image(fill_color="blue", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer,format="PNG")
    buffer.seek(0)
    return buffer.read()
def send_invitation(guest_name : str, guest_email : str, event_name : str, event_date : str, event_id : int):
    qr_data =f"CHECKINIQ|event={event_id}|email={guest_email}"
    qr_bytes= generate_qr_bytes(qr_data)
    msg = MIMEMultipart("related")
    msg["Subject"] = f"Your Invitation — {event_name}"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = guest_email
    #----------HTML BODY-------------
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
        <h2 style="color:#3b5ff7;">You're Invited! 🎉</h2>
        <p>Hi <strong>{guest_name}</strong>,</p>
        <p>You have been invited to <strong>{event_name}</strong>
           on <strong>{event_date}</strong>.</p>
        <p>Please show the QR code below at the entrance for check-in:</p>
        <div style="text-align:center;margin:24px 0;">
            <img src="cid:qrcode" width="180" height="180"/>
        </div>
        <p style="color:#888;font-size:12px;">
            This QR code is unique to you. Do not share it.
        </p>
        <p>See you there! — CheckIn IQ</p>
    </div>
    """
    msg.attach(MIMEText(html_body,"html"))
    qr_attachment = MIMEImage(qr_bytes, name ="checkin_qr.png")
    qr_attachment.add_header("Content-ID","<qrcode>")
    qr_attachment.add_header("Content-Disposition", "inline")
    msg.attach(qr_attachment)
    try:
        _smtp_client.send(msg, guest_email)
        print("✓ Email sent")
        return True
    except Exception as e:
       print(f"[FAILED AT] {e}")
       return False
#--------------------RESET email ------------------
def send_reset_email(name, email, reset_link):
    msg = MIMEMultipart()
    msg["Subject"] = "Reset your CheckInIQ password"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = email

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
        <h2 style="color:#4a7cff;">Password Reset Request</h2>
        <p>Hi <strong>{name}</strong>,</p>
        <p>We received a request to reset your CheckInIQ password.</p>
        <p>Click the button below to reset it. This link expires in <strong>1 hour</strong>.</p>
        <div style="text-align:center;margin:28px 0;">
            <a href="{reset_link}" 
               style="background:linear-gradient(135deg,#3b5ff7,#6366f1);color:#fff;
                      padding:14px 32px;border-radius:8px;text-decoration:none;
                      font-weight:700;font-size:0.95rem;">
                Reset Password
            </a>
        </div>
        <p style="color:#888;font-size:0.8rem;">
            If you didn't request this, ignore this email. Your password won't change.
        </p>
        <p>— CheckIn IQ</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        _smtp_client.send(msg, email)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False  
def send_postpone_email(guest_name,guest_email,event_name,reason,new_date,new_time,new_venue):
    msg = MIMEMultipart()
    msg["Subject"] = f"Event Postponed — {event_name}"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = guest_email
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
        <h2 style="color:#ffb830;">Event Postponed</h2>
        <p>Hi <strong>{guest_name}</strong>,</p>
        <p><strong>{event_name}</strong> has been postponed.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>
        <strong>New Date:</strong> {new_date}<br>
        <strong>New Time:</strong> {new_time}<br>
        <strong>New Venue:</strong> {new_venue}
        </p>
        <p>Your existing QR code will still work at the new date.</p>
        <p>— CheckIn IQ</p>
    </div>"""
    msg.attach(MIMEText(html, "html"))
    try:
        _smtp_client.send(msg, guest_email)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_cancel_email(guest_name, guest_email, event_name, reason):
    msg = MIMEMultipart()
    msg["Subject"] = f"Event Cancelled — {event_name}"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = guest_email
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
        <h2 style="color:#ff5252;">Event Cancelled</h2>
        <p>Hi <strong>{guest_name}</strong>,</p>
        <p>We regret to inform you that <strong>{event_name}</strong> has been cancelled.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>We apologize for any inconvenience.</p>
        <p>— CheckIn IQ</p>
    </div>"""
    msg.attach(MIMEText(html, "html"))
    try:
        _smtp_client.send(msg, guest_email)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False



#----------ID CARD--------------
# ============================================================
# PERSISTENT CHROMIUM BROWSER
# ------------------------------------------------------------
# Before: render_html_to_png() launched a brand-new Chromium
# process (p.chromium.launch()) for EVERY single ID card, then
# closed it. Launching Chromium is slow (1-3s) and memory heavy,
# so a burst of check-ins meant a burst of Chromium processes
# starting at once -> the whole app would lag or the browser
# would appear to "reset".
#
# Now: Chromium is launched ONCE (lazily, on first use) and kept
# alive for the lifetime of the app. Each card only opens a
# lightweight *page* in that already-running browser and closes
# the page (not the browser) when done - this is fast.
#
# IMPORTANT: Playwright's sync API is only safe to call from the
# single thread that created it. That's exactly what bg_worker.py
# does below - it owns this browser and is the ONLY thread that
# should call render_html_to_png / generate_id_card.
# ============================================================
_playwright_ctx = None
_browser = None


def get_persistent_browser():
    """Lazily launch Chromium once and keep reusing the same instance.
    Must only be called from the dedicated background-worker thread."""
    global _playwright_ctx, _browser
    if _browser is None:
        _playwright_ctx = sync_playwright().start()
        _browser = _playwright_ctx.chromium.launch(args=["--no-sandbox"])
    return _browser


def render_html_to_png(html: str, browser=None, width: int = 600, height: int = 360) -> bytes:
    """Render `html` to a PNG.
    - Pass an already-running `browser` (recommended) to reuse it - fast,
      no launch overhead.
    - If no browser is passed, one is launched and closed just for this
      call - slow, only meant for one-off / manual runs (e.g. testing
      from the command line)."""
    if browser is not None:
        page = browser.new_page(viewport={"width": width, "height": height},
                                 device_scale_factor=2)
        try:
            page.set_content(html, wait_until="networkidle")
            card_el = page.query_selector(".card")
            return card_el.screenshot() if card_el else page.screenshot()
        finally:
            page.close()
    else:
        with sync_playwright() as p:
            one_off_browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                return render_html_to_png(html, browser=one_off_browser,
                                           width=width, height=height)
            finally:
                one_off_browser.close()


def generate_id_card(guest_name, event_name, event_date, event_venue, guest_id, qr_bytes, browser=None):
    html = card_midnight(
        guest_name,
        event_name or "TBA",
        str(event_date or "TBA"),
        str(event_venue or "TBA"),
        guest_id,
        qr_bytes,
    )
    return render_html_to_png(html, browser=browser)


#--------------------OTP email for registartion  ------------------
def send_otp_email(name, email, otp):
    msg = MIMEMultipart()
    msg["Subject"] = "Your CheckInIQ verification code"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = email

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;background:#07091a;color:#e8eeff;padding:28px;border-radius:12px;">
        <h2 style="color:#6b9aff;">Verify your email</h2>
        <p>Hi <strong>{name}</strong>,</p>
        <p>Use the code below to finish creating your CheckInIQ account. It expires in <strong>10 minutes</strong>.</p>
        <div style="text-align:center;margin:28px 0;">
            <span style="display:inline-block;background:#1a2550;color:#ffffff;font-size:1.8rem;font-weight:800;letter-spacing:8px;padding:14px 24px;border-radius:10px;">{otp}</span>
        </div>
        <p style="color:#888;font-size:0.8rem;">
            If you didn't try to create an account, you can ignore this email.
        </p>
        <p>— CheckIn IQ</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        _smtp_client.send(msg, email)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False
#-----------ID card Send----------

def send_id_card_email(guest_name, guest_email, event_name, event_date, event_venue, guest_id, qr_bytes, browser=None):
    """Generate the ID card and email it.
    Pass `browser` (a persistent Playwright browser - see
    get_persistent_browser()) so card rendering doesn't launch a new
    Chromium process every time. This is called by bg_worker.py."""
    try:
        card_bytes = generate_id_card(
            guest_name, event_name, event_date,
            event_venue, guest_id, qr_bytes, browser=browser
        )

        msg = MIMEMultipart("related")
        msg["Subject"] = f"Your Entry Pass — {event_name}"
        msg["From"]    = EMAIL_ADDRESS
        msg["To"]      = guest_email

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;background:#07091a;color:#e8eeff;padding:28px;border-radius:12px;">
            <h2 style="color:#6b9aff;">✅ You're Checked In!</h2>
            <p>Hi <strong>{guest_name}</strong>,</p>
            <p>You have successfully checked in to <strong>{event_name}</strong>.</p>
            <p>Your electronic ID card is attached below. You can show this at any point during the event.</p>
            <div style="text-align:center;margin:24px 0;">
                <img src="cid:idcard" width="500" style="border-radius:12px;max-width:100%;"/>
            </div>
            <p style="color:#888;font-size:12px;">
                This ID card is unique to you and linked to your check-in record.
            </p>
            <p>Enjoy the event! — CheckIn IQ</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        card_attachment = MIMEImage(card_bytes, name="id_card.png")
        card_attachment.add_header("Content-ID", "<idcard>")
        card_attachment.add_header("Content-Disposition", "inline", filename="id_card.png")
        msg.attach(card_attachment)

        _smtp_client.send(msg, guest_email)
        print(f"✓ ID card sent to {guest_email}")
        return True

    except Exception as e:
        import traceback
        print(f"[ID CARD EMAIL ERROR] {e}")
        traceback.print_exc()
        return False
if __name__ == "__main__":
    result = send_invitation(
        guest_name  = "Test Guest",
        guest_email = "voidsignal70@gmail.com",  # send to yourself
        event_name  = "CheckIn IQ Demo",
        event_date  = "June 30, 2025",
        event_id    = 1
    )
    print("Sent!" if result else "Failed — check the error above")