# ============================================================
# reports_pdf.py — professional branded PDF report generation
# All reports share one letterhead: college logo + event logo
# + CheckIn IQ logo, rendered via Playwright (HTML -> PDF).
# ============================================================
import base64
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR   = os.path.join(BASE_DIR, "static", "assets")
COLLEGE_LOGO = os.path.join(ASSETS_DIR, "college_logo.png")
CHECKINIQ_LOGO = os.path.join(ASSETS_DIR, "checkiniq_logo.png")
SDC_LOGO = os.path.join(ASSETS_DIR, "sdc_logo.png")


def _data_uri(path, mime="image/png"):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _event_logo_uri(event):
    """Uses the club/event logo uploaded by the organizer, if any."""
    logo_path = event["logo_path"] if event and "logo_path" in event.keys() else None
    if logo_path:
        full = os.path.join(BASE_DIR, logo_path.lstrip("/"))
        if os.path.exists(full):
            ext = os.path.splitext(full)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            return _data_uri(full, mime)
    return ""


def fmt_date(d):
    if not d:
        return "TBA"
    for f in ("%Y-%m-%d", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(d, f).strftime("%d %b %Y")
        except Exception:
            continue
    return d


def fmt_dt(d, out="%d %b %Y, %I:%M %p"):
    if not d:
        return "—"
    try:
        return datetime.strptime(d, "%Y-%m-%d %H:%M:%S").strftime(out)
    except Exception:
        return d


def fmt_time(d):
    return fmt_dt(d, "%I:%M %p")


# ------------------------------------------------------------
# SHARED CSS
# ------------------------------------------------------------
BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
  color:#1a1a2e; font-size:11px; line-height:1.5;
}
.letterhead {
  padding-bottom:14px; border-bottom:2.5px solid #7c5cfc;
  margin-bottom:20px;
}
.letterhead-logos {
  display:grid; grid-template-columns:1fr auto 1fr;
  align-items:center; margin-bottom:14px;
}
.letterhead-logos .checkiniq-chip {
  justify-self:start; background:#0d0b22; border-radius:10px; padding:8px 14px;
  display:inline-flex; align-items:center;
}
.letterhead-logos .checkiniq-chip img { height:20px; }
..letterhead-logos .college { justify-self:center; }
.letterhead-logos .college img { height:44px; }
.letterhead-logos .event-block {
  justify-self:end; display:flex; align-items:center; gap:10px;
}
.event-logo {
  width:44px; height:44px; border-radius:10px; object-fit:contain;
  border:1.5px solid #e3ddff; background:#f6f4ff; padding:3px;
}
.event-logo-placeholder {
  width:44px; height:44px; border-radius:10px; background:#f0edff;
  border:1.5px solid #e3ddff; display:flex; align-items:center; justify-content:center;
  font-size:18px; color:#7c5cfc;
}
.sdc-chip {
  height:44px; border-radius:10px; background:#0d0b22;
  display:flex; align-items:center; padding:0 10px;
}
.sdc-chip img { height:24px; }
}
.letterhead-title { text-align:center; }
.report-title { font-size:20px; font-weight:800; color:#241a52; letter-spacing:0.3px; }
.report-sub { font-size:10.5px; color:#6b6b83; margin-top:2px; }

.meta-strip {
  display:flex; gap:22px; flex-wrap:wrap; background:#f8f7ff; border:1px solid #ece8ff;
  border-radius:10px; padding:12px 16px; margin-bottom:18px;
}
.meta-item .label { font-size:8.5px; font-weight:700; letter-spacing:0.5px; color:#8b7fc7; text-transform:uppercase; }
.meta-item .value { font-size:12.5px; font-weight:700; color:#1a1a2e; margin-top:2px; }

.stats-row { display:flex; gap:12px; margin-bottom:20px; }
.stat-box {
  flex:1; background:linear-gradient(160deg,#f8f7ff,#f1eeff); border:1px solid #e6e1ff;
  border-radius:10px; padding:12px 14px;
}
.stat-box .num { font-size:20px; font-weight:800; color:#4a2ea8; }
.stat-box .lbl { font-size:8.5px; font-weight:700; color:#7a72a3; letter-spacing:0.4px; text-transform:uppercase; margin-top:2px; }

table { width:100%; border-collapse:collapse; margin-bottom:16px; }
thead th {
  background:#241a52; color:#fff; font-size:9.5px; text-transform:uppercase;
  letter-spacing:0.4px; text-align:left; padding:8px 10px; font-weight:700;
}
tbody td { padding:7px 10px; font-size:10.5px; border-bottom:1px solid #eee6ff; }
tbody tr:nth-child(even) { background:#faf9ff; }
.badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:9px; font-weight:700; }
.badge-in  { background:#e3fbe9; color:#1a8a4a; }
.badge-out { background:#fdecec; color:#c0392b; }

.section-title {
  font-size:12.5px; font-weight:800; color:#241a52; margin:18px 0 8px 0;
  padding-bottom:4px; border-bottom:1.5px solid #ece8ff;
}
.noshow-box { background:#fff8f6; border:1px solid #ffdcd3; border-radius:10px; padding:12px 14px; }
.noshow-box .names { font-size:10.5px; color:#8a3a2a; line-height:1.8; }

.bar-row { display:flex; align-items:center; gap:10px; margin-bottom:9px; }
.bar-label { width:150px; font-size:10px; font-weight:600; color:#333; flex-shrink:0; }
.bar-track { flex:1; height:14px; background:#f0edff; border-radius:7px; overflow:hidden; }
.bar-fill  { height:100%; background:linear-gradient(90deg,#7c5cfc,#4a7cff); border-radius:7px; }
.bar-val   { width:46px; text-align:right; font-size:10px; font-weight:700; color:#4a2ea8; }

.sig-cell { border-bottom:1px solid #ccc; }

.footer-note { margin-top:22px; font-size:9px; color:#a8a3c2; text-align:center; }
"""


def _letterhead(event, title, subtitle=""):
    college_uri = _data_uri(COLLEGE_LOGO)
    checkiniq_uri = _data_uri(CHECKINIQ_LOGO)
    sdc_uri = _data_uri(SDC_LOGO)
    event_logo = _event_logo_uri(event) if event else ""
    event_name = event["name"] if event else "All Events"

    if event_logo:
        logo_html = f'<img class="event-logo" src="{event_logo}">'
    else:
        logo_html = '<div class="event-logo-placeholder">🎓</div>'

    sdc_html = f'<div class="sdc-chip"><img src="{sdc_uri}"></div>' if sdc_uri else ''

    return f"""
    <div class="letterhead">
      <div class="letterhead-logos">
        <div class="checkiniq-chip">{f'<img src="{checkiniq_uri}">' if checkiniq_uri else ''}</div>
        <div class="college">{f'<img src="{college_uri}">' if college_uri else ''}</div>
        <div class="event-block">{logo_html}{sdc_html}</div>
      </div>
      <div class="letterhead-title">
        <div class="report-title">{title}</div>
        <div class="report-sub">{subtitle or event_name}</div>
      </div>
    </div>
    """


def _wrap(body_html):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head>
<body>{body_html}</body></html>"""


def _pdf_from_html(html, landscape=False):
    generated = datetime.now().strftime("%d %b %Y, %I:%M %p")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            landscape=landscape,
            print_background=True,
            margin={"top": "16mm", "bottom": "16mm", "left": "13mm", "right": "13mm"},
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=f"""
              <div style="font-size:8px;width:100%;text-align:center;color:#999;
                          font-family:Arial, sans-serif;">
                CheckIn IQ &middot; Generated {generated} &middot;
                Page <span class="pageNumber"></span> of <span class="totalPages"></span>
              </div>"""
        )
        browser.close()
    return pdf_bytes


# ------------------------------------------------------------
# 1) ATTENDANCE SUMMARY
# ------------------------------------------------------------
def attendance_summary_pdf(event, guests):
    checked_in = [g for g in guests if g["status"] == "checked_in"]
    no_shows   = [g for g in guests if g["status"] != "checked_in"]
    total = len(guests)
    rate  = round((len(checked_in) / total) * 100, 1) if total else 0

    checked_in_sorted = sorted(
        checked_in,
        key=lambda g: g["checked_in_at"] or ""
    )

    rows = "".join(f"""
      <tr>
        <td>{i+1}</td>
        <td>{g['name']}</td>
        <td>{g['email']}</td>
        <td>{fmt_dt(g['checked_in_at'])}</td>
        <td><span class="badge badge-in">Checked In</span></td>
      </tr>
    """ for i, g in enumerate(checked_in_sorted))

    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;color:#999;padding:14px;">No check-ins recorded yet.</td></tr>'

    noshow_names = ", ".join(g["name"] for g in no_shows) if no_shows else "None — full attendance! 🎉"

    body = f"""
    {_letterhead(event, "ATTENDANCE SUMMARY REPORT")}
    <div class="meta-strip">
      <div class="meta-item"><div class="label">Event</div><div class="value">{event['name']}</div></div>
      <div class="meta-item"><div class="label">Date</div><div class="value">{fmt_date(event['date'])}</div></div>
      <div class="meta-item"><div class="label">Venue</div><div class="value">{event['location'] or 'TBA'}</div></div>
    </div>
    <div class="stats-row">
      <div class="stat-box"><div class="num">{total}</div><div class="lbl">Total Invited</div></div>
      <div class="stat-box"><div class="num">{len(checked_in)}</div><div class="lbl">Checked In</div></div>
      <div class="stat-box"><div class="num">{len(no_shows)}</div><div class="lbl">No-Shows</div></div>
      <div class="stat-box"><div class="num">{rate}%</div><div class="lbl">Attendance Rate</div></div>
    </div>
    <div class="section-title">Guest Check-In Log</div>
    <table>
      <thead><tr><th style="width:30px;">#</th><th>Name</th><th>Email</th><th>Check-In Time</th><th>Status</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="section-title">Did Not Attend ({len(no_shows)})</div>
    <div class="noshow-box"><div class="names">{noshow_names}</div></div>
    <div class="footer-note">This report was generated automatically by CheckIn IQ.</div>
    """
    return _pdf_from_html(_wrap(body))


# ------------------------------------------------------------
# 2) EVENT COMPARISON
# ------------------------------------------------------------
def event_comparison_pdf(events_with_guests):
    """events_with_guests: list of (event_row, guests_list) ordered chronologically."""
    seen_emails = set()
    rows_html = ""
    bar_html  = ""
    max_checked = max([len([g for g in gl if g["status"] == "checked_in"]) for _, gl in events_with_guests], default=0) or 1

    summary_rows = []
    for event, guests in events_with_guests:
        checked = [g for g in guests if g["status"] == "checked_in"]
        emails_here = set(g["email"] for g in checked)
        new_count = len(emails_here - seen_emails)
        returning_count = len(emails_here & seen_emails)
        seen_emails |= emails_here
        total = len(guests)
        rate = round((len(checked) / total) * 100, 1) if total else 0
        summary_rows.append({
            "event": event, "total": total, "checked": len(checked),
            "rate": rate, "new": new_count, "returning": returning_count
        })

    for r in summary_rows:
        rows_html += f"""
          <tr>
            <td>{r['event']['name']}</td>
            <td>{fmt_date(r['event']['date'])}</td>
            <td>{r['total']}</td>
            <td>{r['checked']}</td>
            <td>{r['rate']}%</td>
            <td>{r['new']}</td>
            <td>{r['returning']}</td>
          </tr>"""

    for r in summary_rows:
        pct = round((r["checked"] / max_checked) * 100) if max_checked else 0
        bar_html += f"""
          <div class="bar-row">
            <div class="bar-label">{r['event']['name'][:22]}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%;"></div></div>
            <div class="bar-val">{r['checked']}</div>
          </div>"""

    if len(summary_rows) >= 2 and summary_rows[0]["checked"] > 0:
        growth = round(((summary_rows[-1]["checked"] - summary_rows[0]["checked"]) / summary_rows[0]["checked"]) * 100, 1)
        growth_txt = f"{'+' if growth >= 0 else ''}{growth}% attendance change from your first event to your most recent."
    else:
        growth_txt = "Not enough events yet to calculate a growth trend."

    total_unique = len(seen_emails)

    body = f"""
    {_letterhead(None, "EVENT COMPARISON REPORT", "Side-by-side performance across all your events")}
    <div class="stats-row">
      <div class="stat-box"><div class="num">{len(summary_rows)}</div><div class="lbl">Events Compared</div></div>
      <div class="stat-box"><div class="num">{total_unique}</div><div class="lbl">Unique Attendees</div></div>
      <div class="stat-box"><div class="num">{sum(r['checked'] for r in summary_rows)}</div><div class="lbl">Total Check-Ins</div></div>
    </div>
    <div class="section-title">Attendance by Event</div>
    <table>
      <thead><tr><th>Event</th><th>Date</th><th>Invited</th><th>Checked In</th><th>Rate</th><th>New Guests</th><th>Returning</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div class="section-title">Check-Ins Per Event</div>
    {bar_html}
    <div class="section-title">Overall Growth</div>
    <div class="noshow-box" style="background:#f6faff;border-color:#d9e8ff;">
      <div class="names" style="color:#2a4a8a;">{growth_txt}</div>
    </div>
    <div class="footer-note">This report was generated automatically by CheckIn IQ.</div>
    """
    return _pdf_from_html(_wrap(body))


# ------------------------------------------------------------
# 3) EXPORT GUEST LIST (with signature column)
# ------------------------------------------------------------
def guest_list_export_pdf(event, guests):
    guests_sorted = sorted(guests, key=lambda g: g["name"].lower())
    rows = "".join(f"""
      <tr>
        <td>{i+1}</td>
        <td>{g['name']}</td>
        <td>{g['email']}</td>
        <td>{'<span class="badge badge-in">Checked In</span>' if g['status']=='checked_in' else '<span class="badge badge-out">Pending</span>'}</td>
        <td>{fmt_dt(g['checked_in_at'])}</td>
        <td class="sig-cell">&nbsp;</td>
      </tr>
    """ for i, g in enumerate(guests_sorted))

    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;color:#999;padding:14px;">No guests on this event yet.</td></tr>'

    body = f"""
    {_letterhead(event, "GUEST LIST", "Official export for on-site verification & sign-in")}
    <div class="meta-strip">
      <div class="meta-item"><div class="label">Event</div><div class="value">{event['name']}</div></div>
      <div class="meta-item"><div class="label">Date</div><div class="value">{fmt_date(event['date'])}</div></div>
      <div class="meta-item"><div class="label">Venue</div><div class="value">{event['location'] or 'TBA'}</div></div>
      <div class="meta-item"><div class="label">Total Guests</div><div class="value">{len(guests)}</div></div>
    </div>
    <table>
      <thead><tr><th style="width:28px;">#</th><th>Name</th><th>Email</th><th>Status</th><th>Check-In Time</th><th style="width:110px;">Signature</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="footer-note">Signature column is provided for organizers who require a secondary, in-person verification alongside QR check-in.</div>
    """
    return _pdf_from_html(_wrap(body))


# ------------------------------------------------------------
# 4) CHECK-IN SPEED REPORT
# ------------------------------------------------------------
def checkin_speed_pdf(event, guests):
    checked = [g for g in guests if g["status"] == "checked_in" and g["checked_in_at"]]
    checked_sorted = sorted(checked, key=lambda g: g["checked_in_at"])

    gaps = []
    for i in range(1, len(checked_sorted)):
        t1 = datetime.strptime(checked_sorted[i-1]["checked_in_at"], "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(checked_sorted[i]["checked_in_at"], "%Y-%m-%d %H:%M:%S")
        gap_sec = (t2 - t1).total_seconds()
        gaps.append({"from": checked_sorted[i-1], "to": checked_sorted[i], "sec": gap_sec})

    avg_sec = sum(g["sec"] for g in gaps) / len(gaps) if gaps else 0
    fastest = min(gaps, key=lambda g: g["sec"]) if gaps else None
    slowest = max(gaps, key=lambda g: g["sec"]) if gaps else None

    first_time = checked_sorted[0]["checked_in_at"] if checked_sorted else None
    last_time  = checked_sorted[-1]["checked_in_at"] if checked_sorted else None
    window_min = 0
    if first_time and last_time:
        window_min = round((datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S") -
                             datetime.strptime(first_time, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60, 1)

    threshold = max(avg_sec * 2, 300)  # flag gaps over 2x average or 5 min as a bottleneck
    delays = [g for g in gaps if g["sec"] > threshold]

    delay_rows = "".join(f"""
      <tr>
        <td>{g['from']['name']} → {g['to']['name']}</td>
        <td>{fmt_time(g['from']['checked_in_at'])} → {fmt_time(g['to']['checked_in_at'])}</td>
        <td>{round(g['sec']/60,1)} min</td>
      </tr>""" for g in sorted(delays, key=lambda x: -x["sec"])[:10])
    if not delay_rows:
        delay_rows = '<tr><td colspan="3" style="text-align:center;color:#999;padding:12px;">No significant delays detected — smooth check-in flow. 🎉</td></tr>'

    # simple per-10-min bucket volume bars
    buckets = {}
    for g in checked_sorted:
        t = datetime.strptime(g["checked_in_at"], "%Y-%m-%d %H:%M:%S")
        bucket_key = t.replace(minute=(t.minute // 10) * 10, second=0)
        buckets.setdefault(bucket_key, 0)
        buckets[bucket_key] += 1
    max_bucket = max(buckets.values(), default=0) or 1
    bucket_html = ""
    for k in sorted(buckets.keys()):
        pct = round((buckets[k] / max_bucket) * 100)
        bucket_html += f"""
          <div class="bar-row">
            <div class="bar-label">{k.strftime('%I:%M %p')}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%;"></div></div>
            <div class="bar-val">{buckets[k]}</div>
          </div>"""
    if not bucket_html:
        bucket_html = '<div style="color:#999;">No check-in activity yet.</div>'

    body = f"""
    {_letterhead(event, "CHECK-IN SPEED REPORT", "Queue pace, bottlenecks & timing analysis")}
    <div class="meta-strip">
      <div class="meta-item"><div class="label">Event</div><div class="value">{event['name']}</div></div>
      <div class="meta-item"><div class="label">First Check-In</div><div class="value">{fmt_time(first_time) if first_time else '—'}</div></div>
      <div class="meta-item"><div class="label">Last Check-In</div><div class="value">{fmt_time(last_time) if last_time else '—'}</div></div>
      <div class="meta-item"><div class="label">Total Window</div><div class="value">{window_min} min</div></div>
    </div>
    <div class="stats-row">
      <div class="stat-box"><div class="num">{len(checked_sorted)}</div><div class="lbl">Total Checked In</div></div>
      <div class="stat-box"><div class="num">{round(avg_sec/60,1) if gaps else 0}m</div><div class="lbl">Avg. Gap Between Guests</div></div>
      <div class="stat-box"><div class="num">{round(fastest['sec'],0) if fastest else 0}s</div><div class="lbl">Fastest Gap</div></div>
      <div class="stat-box"><div class="num">{round(slowest['sec']/60,1) if slowest else 0}m</div><div class="lbl">Slowest Gap</div></div>
    </div>
    <div class="section-title">Check-In Volume Timeline (10-min buckets)</div>
    {bucket_html}
    <div class="section-title">Delays & Bottlenecks</div>
    <table>
      <thead><tr><th>Between Guests</th><th>Time Range</th><th>Delay</th></tr></thead>
      <tbody>{delay_rows}</tbody>
    </table>
    <div class="footer-note">This report was generated automatically by CheckIn IQ.</div>
    """
    return _pdf_from_html(_wrap(body))