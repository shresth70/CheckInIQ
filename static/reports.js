// ============================================================
// reports.js — branded PDF report generation
// ============================================================

// ── STATE ──
let reportType        = null;   // 'attendance-summary' | 'checkin-speed' | 'guest-list'
let reportEventId     = null;
let reportEventName   = null;
let reportLogoFile    = null;

const REPORT_META = {
  'attendance-summary': { title: 'Attendance Summary',   endpoint: id => `/api/reports/attendance-summary/${id}` },
  'checkin-speed':       { title: 'Check-In Speed Report', endpoint: id => `/api/reports/checkin-speed/${id}` },
  'guest-list':          { title: 'Export Guest List',    endpoint: id => `/api/reports/guest-list/${id}` },
};

// ── OPEN PICKER: pick an event for a per-event report ──
async function openReportPicker(type) {
  reportType      = type;
  reportEventId   = null;
  reportEventName = null;
  reportLogoFile  = null;

  document.getElementById('report-modal-title').textContent = REPORT_META[type].title;
  document.getElementById('report-step-select').style.display = 'block';
  document.getElementById('report-step-logo').style.display   = 'none';
  document.getElementById('report-logo-input').value = '';
  document.getElementById('report-logo-preview').style.display = 'none';

  const overlay = document.getElementById('report-modal');
  const list    = document.getElementById('report-event-list');
  overlay.classList.add('open');
  list.innerHTML = '<div style="padding:20px;font-size:0.78rem;color:var(--muted);">Loading events…</div>';

  try {
    const res    = await fetch('/api/events');
    const events = await res.json();

    if (!events.length) {
      list.innerHTML = '<div style="padding:20px;font-size:0.78rem;color:var(--muted);">No events yet — create one first.</div>';
      return;
    }

    list.innerHTML = events.map(e => `
      <div onclick='selectReportEvent(${e.id}, ${JSON.stringify(e.name)}, ${JSON.stringify(e.logo_path || "")})'
           style="padding:12px 14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:background 0.15s;"
           onmouseover="this.style.background='rgba(74,124,255,0.08)'"
           onmouseout="this.style.background='rgba(255,255,255,0.03)'">
        <div>
          <div style="font-size:0.85rem;font-weight:600;">${e.name}</div>
          <div style="font-size:0.72rem;color:var(--muted);">${e.date || 'Date TBD'}${e.location ? ' · ' + e.location : ''}</div>
        </div>
        <div style="font-size:0.72rem;color:var(--muted);">${e.logo_path ? '🖼 has logo' : ''}</div>
      </div>
    `).join('');
  } catch (err) {
    list.innerHTML = '<div style="padding:20px;font-size:0.78rem;color:var(--red);">Failed to load events.</div>';
  }
}

function selectReportEvent(id, name, existingLogoPath) {
  reportEventId   = id;
  reportEventName = name;

  document.getElementById('report-step-select').style.display = 'none';
  document.getElementById('report-step-logo').style.display   = 'block';

  const preview    = document.getElementById('report-logo-preview');
  const previewImg = document.getElementById('report-logo-preview-img');
  if (existingLogoPath) {
    previewImg.src = '/' + existingLogoPath;
    preview.style.display = 'flex';
  } else {
    preview.style.display = 'none';
  }
}

function backToReportEventList() {
  document.getElementById('report-step-select').style.display = 'block';
  document.getElementById('report-step-logo').style.display   = 'none';
}

function handleReportLogoSelect(input) {
  const file = input.files[0];
  if (!file) { reportLogoFile = null; return; }
  reportLogoFile = file;

  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById('report-logo-preview-img').src = e.target.result;
    document.getElementById('report-logo-preview').style.display = 'flex';
  };
  reader.readAsDataURL(file);
}

function closeReportModal() {
  document.getElementById('report-modal').classList.remove('open');
}

// ── GENERATE + DOWNLOAD (uploads logo first if one was picked) ──
async function confirmGenerateReport() {
  const btn = document.getElementById('report-generate-btn');
  btn.disabled = true;
  btn.textContent = 'Generating…';

  try {
    if (reportLogoFile) {
      const fd = new FormData();
      fd.append('logo', reportLogoFile);
      const res = await fetch(`/api/events/${reportEventId}/logo`, {
        method: 'POST', body: fd, credentials: 'same-origin'
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(`⚠️ ${err.error || 'Logo upload failed'} — generating without it`);
      }
    }

    const endpoint = REPORT_META[reportType].endpoint(reportEventId);
    showToast(`📄 Generating ${REPORT_META[reportType].title}…`);
    window.location.href = endpoint;
    closeReportModal();
  } catch (err) {
    showToast('❌ Failed to generate report');
  } finally {
    btn.disabled = false;
    btn.textContent = '📥 Generate & Download';
  }
}

// ── EVENT COMPARISON: no event picker needed, covers every event ──
function generateEventComparison() {
  showToast('📄 Generating Event Comparison Report…');
  window.location.href = '/api/reports/event-comparison';
}