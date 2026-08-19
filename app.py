from flask import Flask, request, jsonify
from flask_cors import CORS
from database import init_db, get_connection
from email_service import send_invitation, send_reset_email, send_postpone_email, send_cancel_email, send_id_card_email, send_otp_email, generate_qr_bytes
from bg_worker import enqueue_id_card_email
from flask import Flask, request, jsonify, redirect, send_from_directory, session, send_file
from flask import send_from_directory
from datetime import datetime
import secrets
import random
import threading
from datetime import datetime, timedelta
from flask import send_from_directory
from functools import wraps
import os
import io
import hashlib
from reports_pdf import (
    attendance_summary_pdf,
    event_comparison_pdf,
    guest_list_export_pdf,
    checkin_speed_pdf,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"], supports_credentials=True)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
init_db()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


@app.route("/team/scan/<int:event_id>/<token>")
def team_scan_page(event_id, token):

    event = get_team_event(event_id, token)

    if not event:
        return "Invalid or expired team access link", 403

    return send_from_directory(
        app.root_path,
        "team-scan.html"
    )
def hash_team_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def get_team_event(event_id, token):

    conn = get_connection()

    event = conn.execute(
        "SELECT * FROM events WHERE id = ?",
        (event_id,)
    ).fetchone()

    if not event:
        conn.close()
        return None

    access = conn.execute(
        """
        SELECT *
        FROM event_team_access
        WHERE event_id = ?
        AND token_hash = ?
        AND active = 1
        """,
        (event_id, hash_team_token(token))
    ).fetchone()

    conn.close()

    if not access:
        return None

    return event

@app.route("/api/events/<int:event_id>/team-access", methods=["POST"])
@login_required
def create_team_access(event_id):
    conn = get_connection()

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event or event["user_id"] != session.get("user_id"):
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    token = secrets.token_urlsafe(24)
    token_hash = hash_team_token(token)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check whether this event already has a team-access row
    existing = conn.execute(
        "SELECT * FROM event_team_access WHERE event_id = ?",
        (event_id,)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE event_team_access
            SET token_hash = ?, active = 1, created_at = ?
            WHERE event_id = ?
            """,
            (token_hash, now, event_id)
        )
    else:
        conn.execute(
            """
            INSERT INTO event_team_access
            (event_id, token_hash, active, created_at)
            VALUES (?, ?, 1, ?)
            """,
            (event_id, token_hash, now)
        )

    conn.commit()
    conn.close()

    base_url = request.host_url.rstrip("/")

    return jsonify({
        "success": True,
        "scanner_url": f"{base_url}/team/scan/{event_id}/{token}",
        "log_url": f"{base_url}/team/log/{event_id}/{token}"
    })

@app.route("/api/events/<int:event_id>/team-access", methods=["GET"])
@login_required
def get_team_access_status(event_id):
    """Lets the dashboard know whether a team link already exists for this
    event. We only ever store a hash of the token (never the plaintext), so
    the real link can't be re-displayed here — only right after it's
    (re)generated. This mirrors how API keys / access tokens are usually
    shown."""
    conn = get_connection()

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event or event["user_id"] != session.get("user_id"):
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    access = conn.execute(
        "SELECT * FROM event_team_access WHERE event_id = ? AND active = 1",
        (event_id,)
    ).fetchone()
    conn.close()

    if not access:
        return jsonify({"active": False})

    return jsonify({"active": True, "created_at": access["created_at"]})


@app.route("/api/events/<int:event_id>/team-access", methods=["DELETE"])
@login_required
def revoke_team_access(event_id):
    conn = get_connection()

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event or event["user_id"] != session.get("user_id"):
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    conn.execute(
        "UPDATE event_team_access SET active = 0 WHERE event_id = ?",
        (event_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ============================================================
# TEAM DESK API — used by team-scan.html / team-log.html
# Authenticated only via the (event_id, token) pair, never a login session,
# since these pages are opened by registration-desk staff who don't have
# accounts of their own.
# ============================================================

@app.route("/api/team/event-info", methods=["GET"])
def team_event_info():
    event_id = request.args.get("event_id", type=int)
    token    = request.args.get("token", "")

    event = get_team_event(event_id, token)
    if not event:
        return jsonify({"error": "Invalid or expired team access link"}), 403

    conn = get_connection()
    total = conn.execute(
        "SELECT COUNT(*) c FROM guests WHERE event_id = ?", (event_id,)
    ).fetchone()["c"]
    checked_in = conn.execute(
        "SELECT COUNT(*) c FROM guests WHERE event_id = ? AND status = 'checked_in'",
        (event_id,)
    ).fetchone()["c"]
    conn.close()

    checkin_allowed = event["status"] not in ("cancelled", "postponed")
    checkin_reason  = None
    if event["status"] == "cancelled":
        checkin_reason = "This event has been cancelled — check-in is closed."
    elif event["status"] == "postponed":
        checkin_reason = "This event has been postponed — check-in is paused until the new date."

    return jsonify({
        "name": event["name"],
        "date": event["date"],
        "location": event["location"],
        "checkin_allowed": checkin_allowed,
        "checkin_reason": checkin_reason,
        "total_guests": total,
        "checked_in": checked_in
    })


@app.route("/api/team/verify-qr", methods=["POST"])
def team_verify_qr():
    data     = request.get_json() or {}
    event_id = data.get("event_id")
    token    = data.get("token", "")
    qr_data  = data.get("qr_data", "") or ""

    event = get_team_event(event_id, token)
    
    if not event:
        return jsonify({"valid": False, "message": "Invalid or expired team access link"}), 403

    if event["status"] in ("cancelled", "postponed"):
        return jsonify({"valid": False, "message": "Check-in is currently closed for this event"}), 403

    try:
        parts       = dict(p.split("=") for p in qr_data.split("|")[1:])
        email       = parts.get("email")
        qr_event_id = int(parts.get("event", 0))
    except Exception:
        return jsonify({"valid": False, "message": "Invalid QR code"}), 400

    if not email or qr_event_id != event_id:
        return jsonify({"valid": False, "message": "This QR code is not for this event"}), 400

    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    event_check = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    allowed, msg = checkin_window_status(event_check)
    if not allowed:
        conn.close()
        return jsonify({"valid": False, "message": msg}), 403
    guest = conn.execute(
        "SELECT * FROM guests WHERE email = ? AND event_id = ?", (email, event_id)
    ).fetchone()

    if not guest:
        conn.close()
        return jsonify({"valid": False, "message": "Guest not found"}), 404

    if guest["status"] == "checked_in":
        conn.close()
        return jsonify({"valid": False, "already": True, "name": guest["name"], "message": "Already checked in!"})

    conn.execute(
        "UPDATE guests SET status = 'checked_in', checked_in_at = ? WHERE email = ? AND event_id = ?",
        (now, email, event_id)
    )
    conn.commit()
    guest_full = conn.execute(
        "SELECT * FROM guests WHERE email = ? AND event_id = ?", (email, event_id)
    ).fetchone()
    conn.close()

    qr_bytes = generate_qr_bytes(f"CHECKINIQ|event={event_id}|email={email}")
    enqueue_id_card_email(
        guest_full["name"], guest_full["email"],
        event["name"], event["date"], event["location"],
        guest_full["id"], qr_bytes
    )

    return jsonify({"valid": True, "name": guest["name"], "email": email, "message": "Check-in successful!"})


@app.route("/api/team/guests", methods=["GET"])
def team_guests_search():
    event_id = request.args.get("event_id", type=int)
    token    = request.args.get("token", "")
    q        = (request.args.get("q") or "").strip()

    event = get_team_event(event_id, token)
    if not event:
        return jsonify({"error": "Invalid or expired team access link"}), 403

    conn = get_connection()
    like = f"%{q}%"
    guests = conn.execute(
        """
        SELECT name, email, status FROM guests
        WHERE event_id = ? AND (name LIKE ? OR email LIKE ?)
        ORDER BY name LIMIT 20
        """,
        (event_id, like, like)
    ).fetchall()
    conn.close()

    return jsonify([
        {"name": g["name"], "email": g["email"], "status": g["status"]}
        for g in guests
    ])


@app.route("/api/team/checkin", methods=["POST"])
def team_checkin():
    data     = request.get_json() or {}
    event_id = data.get("event_id")
    token    = data.get("token", "")
    email    = (data.get("email") or "").strip()
    name     = (data.get("name") or "").strip()
    walkin   = bool(data.get("walkin"))

    event = get_team_event(event_id, token)
    if not event:
        return jsonify({"success": False, "message": "Invalid or expired team access link"}), 403

    if event["status"] in ("cancelled", "postponed"):
        return jsonify({"success": False, "message": "Check-in is currently closed for this event"}), 403

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    event_check = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    allowed, msg = checkin_window_status(event_check)
    if not allowed:
        conn.close()
        return jsonify({"success": False, "message": msg}), 403
    guest = conn.execute(
        "SELECT * FROM guests WHERE email = ? AND event_id = ?", (email, event_id)
    ).fetchone()

    if not guest:
        if not walkin:
            conn.close()
            return jsonify({"success": False, "message": "Guest not found — add them as a walk-in"}), 404
        if not name:
            conn.close()
            return jsonify({"success": False, "message": "Name is required for a new guest"}), 400

        conn.execute(
            """INSERT INTO guests (event_id, name, email, status, checked_in_at)
               VALUES (?, ?, ?, 'checked_in', ?)""",
            (event_id, name, email, now)
        )
        conn.commit()
        guest = conn.execute(
            "SELECT * FROM guests WHERE email = ? AND event_id = ?", (email, event_id)
        ).fetchone()

    elif guest["status"] == "checked_in":
        conn.close()
        return jsonify({"success": False, "message": f"{guest['name']} is already checked in"})

    else:
        conn.execute(
            "UPDATE guests SET status = 'checked_in', checked_in_at = ? WHERE email = ? AND event_id = ?",
            (now, email, event_id)
        )
        conn.commit()
        guest = conn.execute(
            "SELECT * FROM guests WHERE email = ? AND event_id = ?", (email, event_id)
        ).fetchone()

    conn.close()

    qr_bytes = generate_qr_bytes(f"CHECKINIQ|event={event_id}|email={email}")
    enqueue_id_card_email(
        guest["name"], guest["email"],
        event["name"], event["date"], event["location"],
        guest["id"], qr_bytes
    )

    return jsonify({"success": True, "name": guest["name"], "message": f"{guest['name']} checked in!"})


@app.route("/api/team/checkins", methods=["GET"])
def team_checkins_log():
    """Powers the live check-in log page — full guest roster + running stats."""
    event_id = request.args.get("event_id", type=int)
    token    = request.args.get("token", "")

    event = get_team_event(event_id, token)
    if not event:
        return jsonify({"error": "Invalid or expired team access link"}), 403

    conn = get_connection()
    guests = conn.execute(
        """
        SELECT name, email, status, checked_in_at FROM guests
        WHERE event_id = ?
        ORDER BY (checked_in_at IS NULL), checked_in_at DESC, name
        """,
        (event_id,)
    ).fetchall()
    conn.close()

    total      = len(guests)
    checked_in = sum(1 for g in guests if g["status"] == "checked_in")

    return jsonify({
        "name": event["name"],
        "date": event["date"],
        "location": event["location"],
        "total_guests": total,
        "checked_in": checked_in,
        "pending": total - checked_in,
        "guests": [
            {
                "name": g["name"],
                "email": g["email"],
                "status": g["status"],
                "checked_in_at": g["checked_in_at"]
            }
            for g in guests
        ]
    })


@app.route("/team/log/<int:event_id>/<token>")
def team_log_page(event_id, token):
    event = get_team_event(event_id, token)
    if not event:
        return "Invalid or expired team access link", 403
    return send_from_directory(app.root_path, "team-log.html")



def owns_event_or_403(conn, event_id):
    """Returns the event row if the current session user owns it, else None."""
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event or event["user_id"] != session.get("user_id"):
        return None
    return event

def _parse_event_start(date_str):
    """Events store date as either 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM'."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def checkin_window_status(event):
    """
    Returns (allowed: bool, message: str) based on the event's start time
    and its checkin_open_min / checkin_close_min offsets.
    If the event has no parseable date, check-in is always allowed
    (keeps old events / manually-added events working).
    """
    start = _parse_event_start(event["date"] if event else None)
    if not start:
        return True, ""

    open_min  = event["checkin_open_min"]  if "checkin_open_min"  in event.keys() and event["checkin_open_min"]  is not None else 30
    close_min = event["checkin_close_min"] if "checkin_close_min" in event.keys() and event["checkin_close_min"] is not None else 60

    window_start = start - timedelta(minutes=open_min)
    window_end   = start + timedelta(minutes=close_min)
    now = datetime.now()

    if now < window_start:
        return False, f"Check-in opens at {window_start.strftime('%I:%M %p')}"
    if now > window_end:
        return False, f"Check-in closed at {window_end.strftime('%I:%M %p')}"
    return True, ""
#-----registration----
@app.route("/api/register", methods=["POST"])
def register():
    data     = request.get_json()
    email    = data.get("email")
    password = data.get("password")
    name     = data.get("name")
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"error": "Email already registered"}), 400

    conn.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 201
#----------Regusiatrtion Verifivsation suing otp ----------
#----REGISTER: request OTP----
@app.route("/api/register/request-otp", methods=["POST"])
def request_register_otp():
    data     = request.get_json()
    email    = data.get("email")
    password = data.get("password")
    name     = data.get("name")

    if not email or not password or not name:
        return jsonify({"error": "Name, email and password are required"}), 400

    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Email already registered"}), 400

    hashed  = hashlib.sha256(password.encode()).hexdigest()
    otp     = str(random.randint(100000, 999999))
    expires = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("DELETE FROM pending_registrations WHERE email = ?", (email,))
    conn.execute(
        "INSERT INTO pending_registrations (name, email, password, otp, expires_at) VALUES (?, ?, ?, ?, ?)",
        (name, email, hashed, otp, expires)
    )
    conn.commit()
    conn.close()

    sent = send_otp_email(name, email, otp)
    if not sent:
        return jsonify({"error": "Could not send OTP email. Check the address and try again."}), 500

    return jsonify({"success": True, "message": "OTP sent to your email"})


#----REGISTER: verify OTP----
@app.route("/api/register/verify-otp", methods=["POST"])
def verify_register_otp():
    data  = request.get_json()
    email = data.get("email")
    otp   = data.get("otp")

    conn    = get_connection()
    pending = conn.execute(
        "SELECT * FROM pending_registrations WHERE email = ? AND otp = ?",
        (email, otp)
    ).fetchone()

    if not pending:
        conn.close()
        return jsonify({"error": "Invalid OTP"}), 400

    expires = datetime.strptime(pending["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires:
        conn.execute("DELETE FROM pending_registrations WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        return jsonify({"error": "OTP expired. Please register again."}), 400

    conn.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (pending["name"], pending["email"], pending["password"])
    )
    conn.execute("DELETE FROM pending_registrations WHERE email = ?", (email,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


#----LOGIN PAGE -----
@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json()
    email    = data.get("email")
    password = data.get("password")

    hashed = hashlib.sha256(password.encode()).hexdigest()

    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, hashed)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    session.clear()
    session["user_id"]    = user["id"]
    session["user_name"]  = user["name"]
    session["user_email"] = user["email"]
    session.permanent     = True

    return jsonify({
        "success": True,
        "redirect": "/dashboard",
        "user": {"id": user["id"], "name": user["name"], "email": user["email"]}

    })
#-----logout------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me", methods=["GET"])
@login_required
def me():
    return jsonify({
        "id": session["user_id"],
        "name": session["user_name"],
        "email": session["user_email"]
    })


 #----------stats----------------
@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():
    uid  = session["user_id"]
    conn = get_connection()
    
    total_events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE user_id = ?", (uid,)
    ).fetchone()[0]
    total_guests = conn.execute(
        "SELECT COUNT(*) FROM guests g JOIN events e ON g.event_id = e.id WHERE e.user_id = ?", (uid,)
    ).fetchone()[0]
    checked_in   = conn.execute(
        "SELECT COUNT(*) FROM guests g JOIN events e ON g.event_id = e.id WHERE e.user_id = ? AND g.status = 'checked_in'", (uid,)
    ).fetchone()[0]
    pending      = total_guests - checked_in

    recent_events = conn.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (uid,)
    ).fetchall()

    recent_checkins = conn.execute(
        """SELECT g.name, g.email FROM guests g
           JOIN events e ON g.event_id = e.id
           WHERE e.user_id = ? AND g.status = 'checked_in'
           ORDER BY g.rowid DESC LIMIT 4""", (uid,)
    ).fetchall()

    conn.close()

    return jsonify({
        "total_events"    : total_events,
        "total_guests"    : total_guests,
        "checked_in"      : checked_in,
        "pending"         : pending,
        "recent_events"   : [dict(e) for e in recent_events],
        "recent_checkins" : [dict(g) for g in recent_checkins]
    })   

@app.route("/api/analytics", methods=["GET"])
@login_required
def get_analytics():
    uid  = session["user_id"]
    conn = get_connection()
    
    total_guests  = conn.execute(
        "SELECT COUNT(*) FROM guests g JOIN events e ON g.event_id = e.id WHERE e.user_id = ?", (uid,)
    ).fetchone()[0]
    checked_in    = conn.execute(
        "SELECT COUNT(*) FROM guests g JOIN events e ON g.event_id = e.id WHERE e.user_id = ? AND g.status='checked_in'", (uid,)
    ).fetchone()[0]
    rate          = round((checked_in/total_guests*100),1) if total_guests else 0
    times = conn.execute("""
        SELECT g.checked_in_at FROM guests g
        JOIN events e ON g.event_id = e.id
        WHERE e.user_id = ? AND g.status='checked_in' AND g.checked_in_at IS NOT NULL
        ORDER BY g.checked_in_at ASC
    """, (uid,)).fetchall()
    avg_minutes = None
    if len(times) >= 2:
        gaps = []
        for i in range(1, len(times)):
            t1 = datetime.strptime(times[i-1][0], "%Y-%m-%d %H:%M:%S")
            t2 = datetime.strptime(times[i][0],   "%Y-%m-%d %H:%M:%S")
            gap = (t2 - t1).total_seconds() / 60
            if gap < 60:  # ignore gaps over 1hr (breaks between sessions)
                gaps.append(gap)
        if gaps:
            avg_minutes = round(sum(gaps)/len(gaps), 1)
    
    by_event = conn.execute("""
        SELECT e.name, COUNT(g.id) as total,
        SUM(CASE WHEN g.status='checked_in' THEN 1 ELSE 0 END) as checked
        FROM events e LEFT JOIN guests g ON e.id=g.event_id
        WHERE e.user_id = ?
        GROUP BY e.id
    """, (uid,)).fetchall()
    
    conn.close()
    return jsonify({
        "rate": rate,
        "total_guests": total_guests,
        "checked_in": checked_in,
        "avg_minutes" : avg_minutes,
        "by_event": [dict(r) for r in by_event]
    })

#--------------------guets------------
@app.route("/api/guests", methods=["GET"])
@login_required
def get_guests():
    conn = get_connection()
    guests = conn.execute("""
        SELECT g.*, e.name as event_name 
        FROM guests g
        LEFT JOIN events e ON g.event_id = e.id
        WHERE e.user_id = ?
        ORDER BY g.rowid DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([dict(g) for g in guests])
#----Event Route------
@app.route("/api/events", methods = ["POST"])
@login_required
def create_event():
    data = request.get_json()
    name = data.get("name")
    date = data.get("date")
    time = data.get("time")
    location = data.get("location")
    checkin_open_before = data.get("checkin_open_before", 30)
    checkin_close_after = data.get("checkin_close_after", 120)
    if not name :
        return jsonify({"error" : "Event naie is required !!!"}), 400

    # combine date + time into one datetime string so check-in window math works
    if date and time:
        combined_date = f"{date}T{time}"
    else:
        combined_date = date

    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO events (name, date, location, user_id, checkin_open_before, checkin_close_after) VALUES (?, ?, ?, ?, ?, ?)",
        (name, combined_date, location, session["user_id"], checkin_open_before, checkin_close_after)
    )
    conn.commit()
    event_id = cursor.lastrowid   
    conn.close()

    return jsonify({"success": True, "event_id": event_id}), 201

#-------chart data ------
@app.route("/api/chart-data", methods=["GET"])
@login_required
def get_chart_data():
    conn = get_connection()
    rows = conn.execute("""
        SELECT date(g.checked_in_at) as day, COUNT(*) as count
        FROM guests g
        JOIN events e ON g.event_id = e.id
        WHERE e.user_id = ? AND g.checked_in_at IS NOT NULL
        GROUP BY date(g.checked_in_at)
        ORDER BY day ASC
        LIMIT 7
    """, (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

#------------ ALL EVENTS ---------------
@app.route("/api/events", methods=["GET"])
@login_required
def get_events():
    conn = get_connection()
    events = conn.execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    conn.close()
    return jsonify([dict(e) for e in events])

#------------Guest list & invitations-------
@app.route("/api/events/<int:event_id>/invite", methods=["POST"])
@login_required
def invite_guests(event_id):
    data   = request.get_json()
    guests = data.get("guests", [])
    if not guests:
        return jsonify({"error": "No guests provided"}), 400
    conn  = get_connection()
    event = owns_event_or_403(conn, event_id)

    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404
    results = []
    for g in guests:
        name  = g.get("name")
        email = g.get("email")
        conn.execute("INSERT INTO guests (event_id, name, email) VALUES (?, ?, ?)",
            (event_id, name, email))
        sent = send_invitation(
            guest_name  = name,
            guest_email = email,
            event_name  = event["name"],
            event_date  = event["date"] or "TBA",
            event_id    = event_id)
        conn.execute("UPDATE guests SET invite_sent = ? WHERE email = ? AND event_id = ?",
            (1 if sent else 0, email, event_id)
        )
        results.append({"name": name, "email": email, "sent": sent})

    conn.commit()
    conn.close()
    return jsonify({"success": True, "results": results})

# --------Check - In guest -----------
@app.route("/api/checkin", methods=["POST"])
def checkin():
    data     = request.get_json()
    email    = data.get("email")
    event_id = data.get("event_id")

    conn = get_connection()
    event_check = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    allowed, msg = checkin_window_status(event_check)
    if not allowed:
        conn.close()
        return jsonify({"success": False, "message": msg}), 403

    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE guests SET status = 'checked_in', checked_in_at=? WHERE email = ? AND event_id = ?",
        (now,email, event_id)
    )
    conn.commit()
    guest_full = conn.execute("SELECT * FROM guests WHERE email=? AND event_id=?", (email, event_id)).fetchone()
    event_full = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    if guest_full and guest_full["email"]:
        qr_data  = f"CHECKINIQ|event={event_id}|email={email}"
        qr_bytes = generate_qr_bytes(qr_data)
        enqueue_id_card_email(
            guest_full["name"],
            guest_full["email"],
            event_full["name"],
            event_full["date"],
            event_full["location"],
            guest_full["id"],
            qr_bytes
        )

    return jsonify({"success": True, "message": f"{email} checked in!"})
#--------------------------------qr-verification --------------
@app.route("/api/verify-qr", methods=["POST"])
def verify_qr():
    data     = request.get_json()
    qr_data  = data.get("qr_data")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        parts    = dict(p.split("=") for p in qr_data.split("|")[1:])
        email    = parts.get("email")
        event_id = int(parts.get("event", 1))
    except:
        return jsonify({"valid": False, "message": "Invalid QR code"}), 400
    conn  = get_connection()
    guest = conn.execute(
        "SELECT * FROM guests WHERE email = ? AND event_id = ?",
        (email, event_id)
    ).fetchone()
    if not guest:
        conn.close()
        return jsonify({"valid": False, "message": "Guest not found"}), 404

    event_check = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    allowed, msg = checkin_window_status(event_check)
    if not allowed:
        conn.close()
        return jsonify({"valid": False, "message": msg}), 403

    if guest["status"] == "checked_in":
        conn.close()
        return jsonify({"valid": False, "already": True, "name": guest["name"], "message": "Already checked in!"}), 200
    conn.execute(
        "UPDATE guests SET status = 'checked_in', checked_in_at=? WHERE email = ? AND event_id = ?",
        (now,email, event_id)
    )
    conn.commit()
    guest_full  = conn.execute("SELECT * FROM guests WHERE email=? AND event_id=?", (email, event_id)).fetchone()
    event_full  = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    qr_data  = f"CHECKINIQ|event={event_id}|email={email}"
    qr_bytes = generate_qr_bytes(qr_data)
    enqueue_id_card_email(
        guest_full["name"],
        guest_full["email"],
        event_full["name"],
        event_full["date"],
        event_full["location"],
        guest_full["id"],
        qr_bytes
    )

    return jsonify({"valid": True, "name": guest["name"], "email": email, "message": "Check-in successful!"})
#------------------------RESET PASSOWRD---------------------
# ── FORGOT PASSWORD ──
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json()
    email = data.get("email")

    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if not user:
        conn.close()
        # don't reveal if email exists or not
        return jsonify({"success": True})

    # generate token
    token   = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        "INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)",
        (email, token, expires)
    )
    conn.commit()
    conn.close()

    # send reset email
    reset_link = f"http://127.0.0.1:5000/reset-password?token={token}"
    send_reset_email(user["name"], email, reset_link)

    return jsonify({"success": True})


# ── RESET PASSWORD PAGE ──
@app.route("/reset-password")
def reset_password_page():
    return send_from_directory(
        "C:/Users/singh/OneDrive/Desktop/checkiniq",
        "checkiniq-reset.html"
    )


# ── RESET PASSWORD SUBMIT ──
@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data     = request.get_json()
    token    = data.get("token")
    password = data.get("password")
    conn = get_connection()
    record = conn.execute(
        "SELECT * FROM password_resets WHERE token=? AND used=0",
        (token,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Invalid or expired link"}), 400

    # check expiry
    expires = datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires:
        conn.close()
        return jsonify({"error": "Reset link has expired"}), 400
    # update password
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn.execute(
        "UPDATE users SET password=? WHERE email=?",
        (hashed, record["email"])
    )
    # mark token as used
    conn.execute(
        "UPDATE password_resets SET used=1 WHERE token=?", (token,)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True}) 
#-----------------------reroeuting ----
@app.route("/")
def index():
    return send_from_directory(
        "C:/Users/singh/OneDrive/Desktop/checkiniq",
        "checkiniq-premium.html"   # ← your landing page filename
    )

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return send_from_directory(
        "C:/Users/singh/OneDrive/Desktop/checkiniq",
        "checkiniq-dashboard-split.html"
    )
# -----POSTPONE EVENT ----
@app.route("/api/events/<int:event_id>/postpone", methods=["POST"])
@login_required
def postpone_event(event_id):
    data      = request.get_json()
    reason    = data.get("reason")
    new_date  = data.get("new_date")
    new_time  = data.get("new_time")
    new_venue = data.get("new_venue")

    conn  = get_connection()
    event = owns_event_or_403(conn, event_id)
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    conn.execute(
        "UPDATE events SET date=?, location=?, status='postponed' WHERE id=?",
        (new_date, new_venue, event_id)
    )
    conn.commit()

    guests = conn.execute("SELECT * FROM guests WHERE event_id=?", (event_id,)).fetchall()
    conn.close()

    notified = 0
    for g in guests:
        sent = send_postpone_email(
    g["name"],
    g["email"],
    event["name"],
    reason,
    new_date,
    new_time,
    new_venue
)
        if sent: notified += 1

    return jsonify({"success": True, "notified": notified})


# -----CANCEL EVENT -----
@app.route("/api/events/<int:event_id>/cancel", methods=["POST"])
@login_required
def cancel_event(event_id):
    data   = request.get_json()
    reason = data.get("reason")

    conn  = get_connection()
    event = owns_event_or_403(conn, event_id)
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    conn.execute("UPDATE events SET status='cancelled' WHERE id=?", (event_id,))
    conn.commit()

    guests = conn.execute("SELECT * FROM guests WHERE event_id=?", (event_id,)).fetchall()
    conn.close()

    notified = 0
    for g in guests:
        sent = send_cancel_email(g["name"], g["email"], event["name"], reason)
        if sent: notified += 1

    return jsonify({"success": True, "notified": notified})
#--------------------------------REPORTS (PDF)--------------------------------
UPLOAD_LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "logos")
os.makedirs(UPLOAD_LOGO_DIR, exist_ok=True)
ALLOWED_LOGO_EXT = {"png", "jpg", "jpeg"}


def _get_event_and_guests(conn, event_id):
    """Helper: fetch an event (ownership-checked) plus its full guest list."""
    event = owns_event_or_403(conn, event_id)
    if not event:
        return None, None
    guests = conn.execute("SELECT * FROM guests WHERE event_id=?", (event_id,)).fetchall()
    return event, guests


def _safe_filename(name):
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)


# -- UPLOAD / REPLACE AN EVENT'S CLUB LOGO (used on its PDF reports) --
@app.route("/api/events/<int:event_id>/logo", methods=["POST"])
@login_required
def upload_event_logo(event_id):
    conn  = get_connection()
    event = owns_event_or_403(conn, event_id)
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    file = request.files.get("logo")
    if not file or file.filename == "":
        conn.close()
        return jsonify({"error": "No file uploaded"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_LOGO_EXT:
        conn.close()
        return jsonify({"error": "Only PNG or JPG/JPEG logos are allowed"}), 400

    filename = f"event_{event_id}.{ext}"
    filepath = os.path.join(UPLOAD_LOGO_DIR, filename)
    file.save(filepath)

    rel_path = f"static/uploads/logos/{filename}"
    conn.execute("UPDATE events SET logo_path=? WHERE id=?", (rel_path, event_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "logo_url": f"/{rel_path}"})


# -- 1) ATTENDANCE SUMMARY REPORT --
@app.route("/api/reports/attendance-summary/<int:event_id>", methods=["GET"])
@login_required
def report_attendance_summary(event_id):
    conn = get_connection()
    event, guests = _get_event_and_guests(conn, event_id)
    conn.close()
    if not event:
        return jsonify({"error": "Event not found"}), 404

    pdf_bytes = attendance_summary_pdf(event, guests)
    filename  = f"Attendance_Summary_{_safe_filename(event['name'])}.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True, download_name=filename)


# -- 2) EVENT COMPARISON REPORT (across all of the organizer's events) --
@app.route("/api/reports/event-comparison", methods=["GET"])
@login_required
def report_event_comparison():
    conn   = get_connection()
    events = conn.execute(
        "SELECT * FROM events WHERE user_id=? ORDER BY date ASC, created_at ASC",
        (session["user_id"],)
    ).fetchall()

    events_with_guests = []
    for e in events:
        guests = conn.execute("SELECT * FROM guests WHERE event_id=?", (e["id"],)).fetchall()
        events_with_guests.append((e, guests))
    conn.close()

    if not events_with_guests:
        return jsonify({"error": "Create at least one event before comparing"}), 400

    pdf_bytes = event_comparison_pdf(events_with_guests)
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True, download_name="Event_Comparison_Report.pdf")


# -- 3) EXPORT GUEST LIST (PDF, with a signature column for on-site verification) --
@app.route("/api/reports/guest-list/<int:event_id>", methods=["GET"])
@login_required
def report_guest_list(event_id):
    conn = get_connection()
    event, guests = _get_event_and_guests(conn, event_id)
    conn.close()
    if not event:
        return jsonify({"error": "Event not found"}), 404

    pdf_bytes = guest_list_export_pdf(event, guests)
    filename  = f"Guest_List_{_safe_filename(event['name'])}.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True, download_name=filename)


# -- 4) CHECK-IN SPEED REPORT --
@app.route("/api/reports/checkin-speed/<int:event_id>", methods=["GET"])
@login_required
def report_checkin_speed(event_id):
    conn = get_connection()
    event, guests = _get_event_and_guests(conn, event_id)
    conn.close()
    if not event:
        return jsonify({"error": "Event not found"}), 404

    pdf_bytes = checkin_speed_pdf(event, guests)
    filename  = f"CheckIn_Speed_{_safe_filename(event['name'])}.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True, download_name=filename)

#----------- SETTINGS -----------
import json as _json

DEFAULT_NOTIFICATIONS = {
    "realtime_alerts":   True,
    "event_reminders":   True,
    "daily_summary":     False,
    "capacity_warnings": True,
}
DEFAULT_CHECKIN_PREFS = {
    "auto_confirm_qr":     True,
    "allow_late_checkins": True,
    "show_capacity_bar":   False,
    "multi_device_sync":   True,
}

def _load_settings_blob(user_row):
    try:
        blob = _json.loads(user_row["settings_json"] or "{}")
    except (ValueError, TypeError):
        blob = {}
    notifications = {**DEFAULT_NOTIFICATIONS, **blob.get("notifications", {})}
    checkin_prefs = {**DEFAULT_CHECKIN_PREFS, **blob.get("checkin_prefs", {})}
    return notifications, checkin_prefs

def _save_settings_section(uid, section, values):
    conn = get_connection()
    row = conn.execute("SELECT settings_json FROM users WHERE id = ?", (uid,)).fetchone()
    try:
        blob = _json.loads(row["settings_json"] or "{}") if row else {}
    except (ValueError, TypeError):
        blob = {}
    blob[section] = values
    conn.execute("UPDATE users SET settings_json = ? WHERE id = ?", (_json.dumps(blob), uid))
    conn.commit()
    conn.close()


@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    uid  = session["user_id"]
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "User not found"}), 404

    notifications, checkin_prefs = _load_settings_blob(user)

    return jsonify({
        "profile": {
            "org_name":    user["org_name"] or "",
            "admin_email": user["admin_email"] or user["email"],
            "timezone":    user["timezone"] or "Asia/Kolkata (IST)",
        },
        "notifications": notifications,
        "checkin_prefs": checkin_prefs,
    })


@app.route("/api/settings/notifications", methods=["POST"])
@login_required
def save_notification_settings():
    data = request.get_json(force=True) or {}
    values = {key: bool(data.get(key, default)) for key, default in DEFAULT_NOTIFICATIONS.items()}
    _save_settings_section(session["user_id"], "notifications", values)
    return jsonify({"success": True, "notifications": values})


@app.route("/api/settings/checkin-preferences", methods=["POST"])
@login_required
def save_checkin_preferences():
    data = request.get_json(force=True) or {}
    values = {key: bool(data.get(key, default)) for key, default in DEFAULT_CHECKIN_PREFS.items()}
    _save_settings_section(session["user_id"], "checkin_prefs", values)
    return jsonify({"success": True, "checkin_prefs": values})


@app.route("/api/settings/profile", methods=["POST"])
@login_required
def save_profile_settings():
    data        = request.get_json(force=True) or {}
    org_name    = (data.get("org_name") or "").strip()
    admin_email = (data.get("admin_email") or "").strip()
    timezone    = (data.get("timezone") or "").strip() or "Asia/Kolkata (IST)"

    conn = get_connection()
    conn.execute(
        "UPDATE users SET org_name = ?, admin_email = ?, timezone = ? WHERE id = ?",
        (org_name, admin_email, timezone, session["user_id"])
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "profile": {"org_name": org_name, "admin_email": admin_email, "timezone": timezone}
    })

@app.route("/api/events/<int:event_id>/checkin-window", methods=["POST"])
@login_required
def update_checkin_window(event_id):
    data = request.get_json()
    open_min  = data.get("checkin_open_min")
    close_min = data.get("checkin_close_min")
    conn = get_connection()
    owns_event_or_403(conn, event_id)
    conn.execute(
        "UPDATE events SET checkin_open_min=?, checkin_close_min=? WHERE id=?",
        (open_min, close_min, event_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})
#----Server ---------
if __name__ == "__main__" :
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)



