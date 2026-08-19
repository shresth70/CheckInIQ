// ============================================================
// team.js — Registration Team Access (generate / copy / regenerate / revoke)
// Wires up the buttons in the "View Event" modal's team-access panel.
// ============================================================

// Reset the panel to its default (no-links-shown) state. Called whenever a
// different event's modal is opened, since the plaintext link is only ever
// known right after it's (re)generated — never re-fetchable afterwards.
function resetTeamAccessPanel() {
  const linksBox = document.getElementById('team-access-links');
  const btn      = document.getElementById('generate-team-access-btn');
  const note     = document.getElementById('team-access-note');

  if (linksBox) linksBox.style.display = 'none';
  if (btn) { btn.style.display = 'block'; btn.disabled = false; btn.textContent = '🔗 Generate Team Access Links'; }
  if (note) note.style.display = 'none';

  const scannerInput = document.getElementById('team-scanner-link');
  const logInput     = document.getElementById('team-log-link');
  if (scannerInput) scannerInput.value = '';
  if (logInput) logInput.value = '';
}

// Called after the View Event modal is populated, so the button reflects
// whether team access is already active for this event.
async function loadTeamAccessStatus(eventId) {
  resetTeamAccessPanel();
  if (!eventId) return;

  const note = document.getElementById('team-access-note');
  const btn  = document.getElementById('generate-team-access-btn');
  if (!note || !btn) return;

  try {
    const res = await fetch(`/api/events/${eventId}/team-access`);
    if (!res.ok) return;
    const data = await res.json();

    if (data.active) {
      note.textContent = '✅ Team access is currently active for this event. Generating again replaces the old link.';
      note.style.display = 'block';
      btn.textContent = '🔗 Generate New Team Access Links';
    }
  } catch (err) {
    console.error('loadTeamAccessStatus error:', err);
  }
}

async function generateTeamAccess(eventId) {
  if (!eventId) return;

  const btn = document.getElementById('generate-team-access-btn');
  const original = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }

  try {
    const res = await fetch(`/api/events/${eventId}/team-access`, { method: 'POST' });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showToast('❌ ' + (data.error || 'Failed to generate team access links'));
      return;
    }

    document.getElementById('team-scanner-link').value = data.scanner_url;
    document.getElementById('team-log-link').value = data.log_url;
    document.getElementById('team-access-links').style.display = 'block';

    const note = document.getElementById('team-access-note');
    if (note) note.style.display = 'none';
    if (btn) btn.style.display = 'none';

    showToast('🔗 Team access links generated — copy and share them now');
  } catch (err) {
    console.error('generateTeamAccess error:', err);
    showToast('❌ Could not reach server');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = original; }
  }
}

async function regenerateTeamAccess(eventId) {
  if (!eventId) return;
  if (!confirm('Regenerating creates a new link and immediately invalidates the old one — anyone still using it will be locked out. Continue?')) return;
  await generateTeamAccess(eventId);
}

async function revokeTeamAccess(eventId) {
  if (!eventId) return;
  if (!confirm('Revoke team access? Both the scanner and live-log links will stop working immediately.')) return;

  try {
    const res = await fetch(`/api/events/${eventId}/team-access`, { method: 'DELETE' });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showToast('❌ Failed to revoke team access');
      return;
    }

    resetTeamAccessPanel();
    showToast('🚫 Team access revoked');
  } catch (err) {
    console.error('revokeTeamAccess error:', err);
    showToast('❌ Could not reach server');
  }
}

function copyTeamLink(inputId) {
  const input = document.getElementById(inputId);
  if (!input || !input.value) return;

  input.select();
  input.setSelectionRange(0, 99999);

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(input.value)
      .then(() => showToast('📋 Link copied'))
      .catch(() => { document.execCommand('copy'); showToast('📋 Link copied'); });
  } else {
    document.execCommand('copy');
    showToast('📋 Link copied');
  }
}