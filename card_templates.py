import base64

def _qr_data_uri(qr_bytes: bytes) -> str:
    b64 = base64.b64encode(qr_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"

CARD_CSS = """
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', Arial, sans-serif; }
body { width:600px; height:360px; }
.card { width:600px; height:360px; border-radius:20px; overflow:hidden; position:relative;
        background: radial-gradient(circle at 85% 15%, #2a1a55 0%, #0d0b22 55%), #0d0b22; color:#fff; }
.card::before { content:''; position:absolute; inset:0; z-index:1;
  background-image: radial-gradient(#7c5cfc33 1.5px, transparent 1.5px); background-size:16px 16px; opacity:0.5; }
.brand-row { display:flex; align-items:center; justify-content:space-between; padding:22px 26px 0 26px; position:relative; z-index:2; }
.brand { display:flex; align-items:center; gap:10px; }
.logo-circle { width:34px; height:34px; border-radius:50%; background:#1a1440; border:1px solid #7c5cfc55;
                display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.logo-circle svg { width:18px; height:18px; }
.brand-text .name { font-size:19px; font-weight:800; line-height:1.1; }
.brand-text .tag { font-size:10px; opacity:0.65; margin-top:2px; }
.card-label { font-size:11px; font-weight:700; letter-spacing:0.5px; color:#a78bfa; }
.guest-name { font-size:23px; font-weight:800; margin-bottom:4px; }
.body-row { display:flex; padding:0 26px; gap:20px; position:relative; z-index:2; margin-top:14px; }
.fields { flex:1; display:flex; flex-direction:column; gap:14px; }
.field-label { font-size:9.5px; font-weight:700; letter-spacing:0.6px; color:#a78bfa; }
.field-value { font-size:13.5px; font-weight:600; margin-top:1px; color:#e9e4ff; }
.qr-box { width:170px; height:170px; background:#fff; border-radius:12px; display:flex; align-items:center;
          justify-content:center; padding:8px; flex-shrink:0; border:2px solid #7c5cfc88; }
.qr-box img { width:100%; height:100%; }
.qr-col { display:flex; flex-direction:column; align-items:center; gap:10px; }
.scan-pill { font-size:11px; font-weight:700; padding:7px 16px; border-radius:20px; display:flex; align-items:center;
             gap:6px; background:#241a52; color:#c9b9ff; border:1px solid #7c5cfc55; }
.footer-row { position:absolute; bottom:16px; left:26px; font-size:11px; font-weight:700; z-index:2; color:#8b74e6; }
"""

def card_midnight(name, event, date, venue, guest_id, qr_bytes):
    check_icon = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#a78bfa" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    body = f"""
    <div class="card">
      <div class="brand-row">
        <div class="brand">
          <div class="logo-circle">{check_icon}</div>
          <div class="brand-text"><div class="name">CheckIn<span style="color:#a78bfa">IQ</span></div>
          <div class="tag">Smart Check-In. Seamless Events.</div></div>
        </div>
        <div class="card-label">EVENT ID CARD</div>
      </div>
      <div style="padding:22px 26px 0 26px;position:relative;z-index:2;">
        <div class="guest-name">{name.upper()}</div>
      </div>
      <div class="body-row">
        <div class="fields">
          <div><div class="field-label">EVENT</div><div class="field-value">{event}</div></div>
          <div><div class="field-label">DATE</div><div class="field-value">{date}</div></div>
          <div><div class="field-label">VENUE</div><div class="field-value">{venue}</div></div>
        </div>
        <div class="qr-col">
          <div class="qr-box"><img src="{_qr_data_uri(qr_bytes)}"></div>
          <div class="scan-pill">⧉ SCAN TO VERIFY</div>
        </div>
      </div>
      <div class="footer-row">ID: #{str(guest_id).zfill(6)}</div>
    </div>"""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CARD_CSS}</style></head><body>{body}</body></html>"""