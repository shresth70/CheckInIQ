// ============================================================
// checkins.js — manual check-in, QR scanner, recent list
// ADD NEW CHECK-IN FEATURES HERE
// ============================================================

// ── LOAD CHECK-INS PAGE ──
async function loadCheckinsPage() {
  // populate event dropdown
  try {
    const res    = await fetch('/api/events');
    const events = await res.json();
    const sel    = document.getElementById('ci-event-select');
    if (sel) {
      sel.innerHTML = events.length
        ? events.map(e => `<option value="${e.id}" style="background:#0d1126">${e.name}</option>`).join('')
        : '<option style="background:#0d1126">No events yet</option>';
    }
  } catch(e) {}

  // populate recent check-ins
  const ciList = document.getElementById('ci-list');
  if (!ciList) return;
  try {
    const res    = await fetch('/api/guests');
    const guests = await res.json();
    const checkedIn = guests.filter(g => g.status === 'checked_in');

    if (!checkedIn.length) {
      ciList.innerHTML = '<div style="padding:12px;font-size:0.78rem;color:var(--muted);">No check-ins yet.</div>';
      return;
    }

    const colors = [
      ['#3b5ff720','#6b9aff'], ['#7c3aed20','#a78bfa'],
      ['#05966920','#34d399'], ['#b4510720','#fb923c']
    ];
    ciList.innerHTML = checkedIn.slice(0, 10).map((g, i) => {
      const initials = (g.name || '??').split(' ').map(w => w[0]).join('').substring(0,2).toUpperCase();
      const c = colors[i % colors.length];
      return `<div class="ci-row">
        <div class="avatar" style="background:${c[0]};color:${c[1]};width:30px;height:30px;font-size:0.65rem;">${initials}</div>
        <div style="flex:1;">
          <div class="ci-name">${g.name}</div>
          <div class="ci-event">${g.event_name || '—'}</div>
        </div>
        <div class="ci-time-badge">✓</div>
      </div>`;
    }).join('');
  } catch(e) {
    ciList.innerHTML = '<div style="padding:12px;font-size:0.78rem;color:var(--red);">Failed to load.</div>';
  }
}

// ── MANUAL CHECK-IN ──
async function doManualCheckin() {
  const guest    = document.getElementById('ci-guest').value.trim();
  const eventId  = parseInt(document.getElementById('ci-event-select').value) || 1;
  if (!guest) { showToast('⚠ Please enter a guest email'); return; }

  try {
    const res  = await fetch('/api/checkin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: guest, event_id: eventId })
    });
    const data = await res.json();
    if (data.success) {
      showToast('✅ ' + guest + ' checked in!');
      document.getElementById('ci-guest').value = '';
      loadCheckinsPage();
      loadDashboardData();
    }
  } catch(err) { showToast('❌ Server not reachable'); }
}

// ── QR SCANNER ──
let scannerActive = false;
let scannerStream = null;
let scannerTimer  = null;

async function toggleScanner() {
  scannerActive ? stopScanner() : startScanner();
}

async function startScanner() {
  try {
    if (!window.jsQR) await loadScript('https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js');

    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    scannerStream = stream;
    const video   = document.getElementById('qr-video');
    video.srcObject = stream;
    await video.play();

    scannerActive = true;
    document.getElementById('qr-toggle-btn').textContent   = '⏹ Stop Scanner';
    document.getElementById('qr-status-label').textContent = 'Scanning… hold QR code steady';
    document.getElementById('scan-line').style.display     = 'block';
    document.getElementById('qr-result').style.display     = 'none';
    scannerTimer = setInterval(scanFrame, 300);
  } catch(err) {
    document.getElementById('qr-status-label').textContent = '❌ Camera access denied';
  }
}

function stopScanner() {
  if (scannerStream) scannerStream.getTracks().forEach(t => t.stop());
  clearInterval(scannerTimer);
  scannerActive = false;
  document.getElementById('qr-toggle-btn').textContent   = '📷 Activate Scanner';
  document.getElementById('qr-status-label').textContent = 'Click activate to start scanning';
  document.getElementById('scan-line').style.display     = 'none';
  document.getElementById('qr-video').srcObject          = null;
}

function scanFrame() {
  const video = document.getElementById('qr-video');
  if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
  const c = document.createElement('canvas');
  c.width = video.videoWidth; c.height = video.videoHeight;
  c.getContext('2d').drawImage(video, 0, 0);
  const img  = c.getContext('2d').getImageData(0, 0, c.width, c.height);
  const code = jsQR(img.data, img.width, img.height);
  if (code) { clearInterval(scannerTimer); processQR(code.data); }
}

async function processQR(qrData) {
  document.getElementById('qr-status-label').textContent = 'Processing…';
  if (!qrData.startsWith('CHECKINIQ|')) {
    showQRResult(false, '❌ Not a CheckInIQ QR code');
    setTimeout(() => { scannerTimer = setInterval(scanFrame, 300); }, 2000);
    return;
  }
  try {
    const res  = await fetch('/api/verify-qr', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ qr_data: qrData })
    });
    const data = await res.json();

    if (data.valid) {
      showQRResult(true, `✅ Welcome, ${data.name}!`);
      const now  = new Date();
      const time = now.getHours() + ':' + String(now.getMinutes()).padStart(2,'0');
      const row  = document.createElement('div');
      row.className = 'ci-row';
      row.innerHTML = `
        <div class="avatar" style="background:#3b5ff720;color:#6b9aff;width:30px;height:30px;font-size:0.65rem;">
          ${data.name.substring(0,2).toUpperCase()}
        </div>
        <div style="flex:1;"><div class="ci-name">${data.name}</div><div class="ci-event">Scanned QR</div></div>
        <div class="ci-time-badge">${time}</div>`;
      const list = document.getElementById('ci-list');
      list.insertBefore(row, list.firstChild);
      loadDashboardData();
    } else if (data.already) {
      showQRResult(false, `⚠️ ${data.name} already checked in!`);
    } else {
      showQRResult(false, `❌ ${data.message}`);
    }
  } catch(err) { showQRResult(false, '❌ Server not reachable'); }

  setTimeout(() => {
    document.getElementById('qr-result').style.display     = 'none';
    document.getElementById('qr-status-label').textContent = 'Scanning…';
    scannerTimer = setInterval(scanFrame, 300);
  }, 3000);
}

function showQRResult(success, message) {
  const el = document.getElementById('qr-result');
  el.textContent      = message;
  el.style.display    = 'block';
  el.style.background = success ? 'rgba(16,217,122,0.12)' : 'rgba(255,82,82,0.12)';
  el.style.color      = success ? 'var(--green)' : 'var(--red)';
  el.style.border     = success ? '1px solid rgba(16,217,122,0.3)' : '1px solid rgba(255,82,82,0.3)';
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src; s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  });
}

// ── EVENT DROPDOWN (alias, called from some inline HTML) ──
async function loadEventDropdown() {
  try {
    const res  = await fetch('/api/events');
    const data = await res.json();
    const sel  = document.getElementById('ci-event-select');
    if (!sel) return;
    sel.innerHTML = data.length
      ? data.map(e => `<option value="${e.id}" style="background:#0d1126">${e.name}</option>`).join('')
      : '<option>No events yet</option>';
  } catch(err) {}
}
