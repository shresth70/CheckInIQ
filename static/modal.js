
// ============================================================

let parsedGuests = [];
let currentStep  = 1;

// -- OPEN / CLOSE --
function openModal() {
  resetModal();
  document.getElementById('modal').classList.add('open');
}
function closeModal() {
  document.getElementById('modal').classList.remove('open');
}
function resetModal() {
  currentStep  = 1;
  parsedGuests = [];
  goStep(1);
  clearFile();
  ['ev-name','ev-venue','ev-desc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const openEl  = document.getElementById('ev-checkin-open');
  const closeEl = document.getElementById('ev-checkin-close');
  if (openEl)  openEl.value  = 30;
  if (closeEl) closeEl.value = 120;
  document.getElementById('send-progress').style.display  = 'none';
  document.getElementById('step3-footer').style.display   = 'flex';
  document.getElementById('send-btn').disabled            = false;
  document.getElementById('send-btn').textContent         = '🚀 Create & Send Invitations';
  document.getElementById('send-btn').onclick             = sendInvitations;
  document.getElementById('modal-title').textContent      = 'Create New Event';
}
document.getElementById('modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

// ---- STEP NAVIGATION ----
function goStep(n) {
  [1,2,3].forEach(i => {
    document.getElementById('step'+i).classList.toggle('active', i === n);
    const sc = document.getElementById('sc'+i);
    const sl = document.getElementById('sl'+i);
    sc.className  = 'step-circle' + (i < n ? ' done' : i === n ? ' active' : '');
    sc.textContent = i < n ? '✓' : i;
    sl.className  = 'step-label' + (i === n ? ' active' : '');
    if (i < 3) document.getElementById('conn'+i).className = 'step-connector' + (i < n ? ' done' : '');
  });
  if (n === 3) populateInvitePreview();
  currentStep = n;
}

function populateInvitePreview() {
  const name  = document.getElementById('ev-name').value.trim()  || 'Your Event';
  const date  = document.getElementById('ev-date').value;
  const time  = document.getElementById('ev-time').value;
  const venue = document.getElementById('ev-venue').value.trim() || 'TBD';
  const fmt   = date
    ? new Date(date + 'T' + (time || '00:00')).toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'})
      + (time ? ' · ' + formatTime(time) : '')
    : 'Date TBD';

  document.getElementById('email-subject-preview').textContent  = "You're invited to " + name;
  document.getElementById('email-ev-name-preview').textContent  = name;
  document.getElementById('email-ev-date-preview').textContent  = fmt;
  document.getElementById('email-ev-venue-preview').textContent = venue;
  document.getElementById('invite-count').textContent           = parsedGuests.length || '—';
}

function formatTime(t) {
  const [h, m] = t.split(':');
  const hr = parseInt(h);
  return ((hr % 12) || 12) + ':' + m + ' ' + (hr >= 12 ? 'PM' : 'AM');
}

// ---- FILE HANDLING ----
function handleFileSelect(input) {
  if (input.files && input.files[0]) processFile(input.files[0]);
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('drag-over');
  if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]);
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function processFile(file) {
  const reader = new FileReader();
  reader.onload = function(e) {
    const text     = e.target.result;
    const rows     = text.trim().split('\n').map(r => r.split(',').map(c => c.trim().replace(/^"|"$/g,'')));
    const header   = rows[0].map(h => h.toLowerCase());
    const nameIdx  = header.findIndex(h => h.includes('name'));
    const emailIdx = header.findIndex(h => h.includes('email') || h.includes('mail'));
    const dataRows = rows.slice(1).filter(r => r.length > 1 && r.some(c => c));

    const allGuests = emailIdx === -1 && nameIdx === -1
      ? dataRows.map(r => ({ name: r[0]||'Unknown', email: r[1]||'' }))
      : dataRows.map(r => ({
          name:  nameIdx  >= 0 ? (r[nameIdx]  || 'Guest') : r[0] || 'Guest',
          email: emailIdx >= 0 ? (r[emailIdx] || '')      : r[1] || ''
        }));

    // split into valid and invalid
    parsedGuests        = allGuests.filter(g => isValidEmail(g.email));
    window.invalidGuests = allGuests.filter(g => !isValidEmail(g.email));

    showFilePreview(file.name, parsedGuests);
    showInvalidPanel(window.invalidGuests);
  };
  reader.readAsText(file);
}
function showFilePreview(filename, guests) {
  document.getElementById('file-chip-name').textContent  = filename;
  document.getElementById('file-chip-count').textContent = guests.length + ' guests found';
  const rows = document.getElementById('guest-preview-rows');
  rows.innerHTML = guests.slice(0,8).map(g =>
    `<div class="gp-row">
      <div>${g.name}</div>
      <div style="color:var(--muted);font-size:0.7rem;">${g.email}</div>
      <div><span class="gp-status">Pending</span></div>
    </div>`
  ).join('') + (guests.length > 8
    ? `<div style="padding:7px 12px;font-size:0.7rem;color:var(--muted);">+${guests.length-8} more…</div>`
    : '');
  document.getElementById('file-preview').style.display  = 'block';
  document.getElementById('no-file-note').style.display  = 'none';
  document.getElementById('upload-zone').style.display   = 'none';
}

function clearFile() {
  parsedGuests = [];
  document.getElementById('file-preview').style.display  = 'none';
  document.getElementById('no-file-note').style.display  = 'block';
  document.getElementById('upload-zone').style.display   = 'block';
  const fi = document.getElementById('guest-file-input');
  if (fi) fi.value = '';
}

// ---- SEND INVITATIONS ----
async function sendInvitations() {
  const name     = document.getElementById('ev-name').value.trim();
  const date     = document.getElementById('ev-date').value.trim();
  const time     = document.getElementById('ev-time').value.trim();
  const location = document.getElementById('ev-venue').value.trim();
  const checkinOpenEl  = document.getElementById('ev-checkin-open');
  const checkinCloseEl = document.getElementById('ev-checkin-close');
  const checkin_open_before = checkinOpenEl  && checkinOpenEl.value  !== '' ? parseInt(checkinOpenEl.value)  : 30;
  const checkin_close_after = checkinCloseEl && checkinCloseEl.value !== '' ? parseInt(checkinCloseEl.value) : 120;

  if (!name) { showToast('⚠ Please fill in the event name first'); goStep(1); return; }

  const guests = parsedGuests.length > 0
    ? parsedGuests
    : [{ name:'Demo Guest', email:'demo@example.com' }];

  const btn = document.getElementById('send-btn');
  btn.disabled    = true;
  btn.textContent = 'Sending…';
  document.getElementById('send-progress').style.display = 'block';
  document.getElementById('step3-footer').style.display  = 'none';

  const log = document.getElementById('send-log');
  const bar = document.getElementById('send-bar');
  const pct = document.getElementById('send-pct');
  log.innerHTML = '';

  try {
    // Step A — create event
    const eventRes  = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, date, time, location, checkin_open_before, checkin_close_after })
    });
    const eventData = await eventRes.json();
    if (!eventData.event_id) { showToast('❌ Failed to create event'); return; }
    window.currentEventId = eventData.event_id; // save for fixAndSend


    // Step B — send invitations
    const inviteRes  = await fetch(`/api/events/${eventData.event_id}/invite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ guests })
    });
    const inviteData = await inviteRes.json();

    // Step C — show results
    inviteData.results.forEach((g, i) => {
      const progress = Math.round(((i+1) / inviteData.results.length) * 100);
      bar.style.width  = progress + '%';
      pct.textContent  = progress + '%';
      const row = document.createElement('div');
      row.className = 'send-log-row';
      row.innerHTML = `
        <span class="tick">✓</span>
        <span>${g.name}</span>
        <span style="color:var(--muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">&lt;${g.email}&gt;</span>
        <span style="color:${g.sent ? 'var(--green)' : 'var(--red)'};">${g.sent ? 'QR sent ✓' : 'Failed ✗'}</span>`;
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
    });

    bar.style.width = '100%'; pct.textContent = '100%';
    setTimeout(() => {
      closeModal();
      showToast(`🎉 "${name}" created! ${guests.length} invitations sent.`);
      loadDashboardData();
      loadEventsTable();
    }, 800);

  } catch(err) {
    showToast('❌ Could not reach server — is Flask running?');
    btn.disabled    = false;
    btn.textContent = '🚀 Create & Send Invitations';
  }
}
// --- Invalid function ------
function showInvalidPanel(invalids) {
  const panel = document.getElementById('invalid-email-panel');
  if (!invalids.length) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = 'block';
  panel.innerHTML = `
    <div style="font-size:0.78rem;font-weight:600;color:var(--amber);margin-bottom:8px;">
      ⚠ ${invalids.length} guest(s) have missing or invalid emails
    </div>
    <div id="invalid-guest-rows">
      ${invalids.map((g, i) => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;" id="invalid-row-${i}">
          <div style="font-size:0.78rem;font-weight:600;min-width:120px;">${g.name}</div>
          <input class="form-input" style="flex:1;padding:6px 10px;font-size:0.75rem;"
            id="fix-email-${i}"
            placeholder="Enter email for ${g.name}"
            value="${g.email || ''}">
          <button class="btn-sm primary" onclick="fixAndSend(${i}, '${g.name.replace(/'/g,"\\'")}')">Send</button>
          <button class="btn-sm ghost" onclick="skipGuest(${i}, '${g.name.replace(/'/g,"\\'")}')">Skip</button>
        </div>
      `).join('')}
    </div>
    <div style="font-size:0.7rem;color:var(--muted);margin-top:6px;">
      Skipped guests will be added to the list but won't receive an invitation.
    </div>
  `;
}
//-----update / fix 
async function fixAndSend(idx, guestName) {
  const emailInput = document.getElementById(`fix-email-${idx}`);
  const email      = emailInput.value.trim();

  if (!isValidEmail(email)) {
    emailInput.style.borderColor = 'var(--red)';
    showToast('⚠ Please enter a valid email');
    return;
  }

  emailInput.style.borderColor = '';
  const row = document.getElementById(`invalid-row-${idx}`);
  row.innerHTML = `<div style="font-size:0.75rem;color:var(--muted);">⏳ Sending to ${guestName}…</div>`;

  // add to parsedGuests so they get sent when main send fires
  // OR if event already created, send directly
  if (window.currentEventId) {
    // event already exists — send immediately
    try {
      const res  = await fetch(`/api/events/${window.currentEventId}/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guests: [{ name: guestName, email }] })
      });
      const data = await res.json();
      const sent = data.results?.[0]?.sent;
      row.innerHTML = sent
        ? `<div style="font-size:0.75rem;color:var(--green);">✅ ${guestName} — QR sent to ${email}</div>`
        : `<div style="font-size:0.75rem;color:var(--red);">❌ ${guestName} — email failed</div>`;
    } catch(err) {
      row.innerHTML = `<div style="font-size:0.75rem;color:var(--red);">❌ Server error</div>`;
    }
  } else {
    // event not created yet — add to parsedGuests for bulk send
    parsedGuests.push({ name: guestName, email });
    row.innerHTML = `<div style="font-size:0.75rem;color:var(--green);">✅ ${guestName} added — will be sent with invitations</div>`;
    document.getElementById('invite-count').textContent = parsedGuests.length;
  }
}

function skipGuest(idx, guestName) {
  const row = document.getElementById(`invalid-row-${idx}`);
  row.innerHTML = `<div style="font-size:0.75rem;color:var(--muted);">⏭ ${guestName} skipped — will be added without email</div>`;
  // add to skipped list for end report
  if (!window.skippedGuests) window.skippedGuests = [];
  window.skippedGuests.push(guestName);
}
// ---- LEGACY STUB ----
function createEvent() {
  const name = document.getElementById('ev-name').value.trim();
  closeModal();
  showToast('🎉 Event "' + (name || 'New Event') + '" created!');
}
if (window.skippedGuests && window.skippedGuests.length > 0) {
  const names = window.skippedGuests.join(', ');
  setTimeout(() => showToast(`⚠ Not notified: ${names} — no email provided`), 1000);
  window.skippedGuests = [];
}
window.currentEventId = null;