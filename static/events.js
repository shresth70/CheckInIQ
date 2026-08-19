// ============================================================
// events.js — events table, view modal, postpone/cancel
// ============================================================
let actionEventId = null;
let currentViewEventId = null;

// ── EVENTS TABLE ──
async function loadEventsTable() {
  const el = document.getElementById('events-table-body');
  if (!el) return;
  try {
    const res  = await fetch('/api/events');
    const data = await res.json();
    const icons = ['💡','📣','🎓','🎤','🏆','🎨'];

    if (!data.length) {
      el.innerHTML = '<div style="padding:16px;font-size:0.78rem;color:var(--muted);">No events yet — create one!</div>';
      return;
    }

    el.innerHTML = data.map((e, i) => {
      let badge = '<span class="event-badge badge-upcoming">Upcoming</span>';
      let rowClass = '';
      if (e.status === 'cancelled') {
        badge = '<span class="event-badge badge-cancelled">🚫 Cancelled</span>';
        rowClass = ' row-cancelled';
      } else if (e.status === 'postponed') {
        badge = '<span class="event-badge badge-postponed">⏳ Postponed</span>';
      } else if (e.date) {
        const eventDate = new Date(e.date);
        const today = new Date(); today.setHours(0,0,0,0);
        if (eventDate < today) badge = '<span class="event-badge badge-ended">Ended</span>';
        else if (eventDate.toDateString() === today.toDateString()) badge = '<span class="event-badge badge-active">Active</span>';
      }

      const reasonNote = e.status === 'cancelled' && e.cancel_reason
        ? `<div class="event-reason-note">Reason: ${e.cancel_reason}</div>`
        : (e.status === 'postponed' && e.postpone_reason
          ? `<div class="event-reason-note">Reason: ${e.postpone_reason}</div>`
          : '');

      return `<div class="table-row${rowClass}">
        <div class="ev-name-cell">
          <div class="ev-ico-sm" style="background:rgba(74,124,255,0.15);">${icons[i % icons.length]}</div>
          <div><div class="ev-nm">${e.name}</div><div class="ev-dt">${e.location || 'No venue'}</div>${reasonNote}</div>
        </div>
        <div>${e.date || 'TBA'}</div>
        <div>${badge}</div>
        <div class="action-btns">
          <button type="button" class="btn-sm primary" onclick="event.stopPropagation(); viewEvent(${e.id})">View</button>
          <button
            type="button"
            class="btn-sm ghost"
            onclick="event.stopPropagation(); editEvent(${e.id})"
            ${e.status === 'cancelled' ? 'disabled title="Cancelled events can\'t be edited"' : ''}
          >
            Edit
          </button>
        </div>
      </div>`;
    }).join('');
  } catch(err) { 
    console.error('loadEventsTable error:', err); 
  }
}

// ── VIEW EVENT MODAL ──
async function viewEvent(eventId) {
  closeActionModal();
  currentViewEventId = eventId;
  
  const guestSelector = document.getElementById('event-select-modal');
  if (guestSelector) guestSelector.classList.remove('open');

  try {
    const [eventsRes, guestsRes] = await Promise.all([fetch('/api/events'), fetch('/api/guests')]);
    const events    = await eventsRes.json();
    const allGuests = await guestsRes.json();

    const event     = events.find(e => e.id === eventId);
    if (!event) return;

    const guests    = allGuests.filter(g => g.event_id === eventId);
    const checkedIn = guests.filter(g => g.status === 'checked_in').length;

    document.getElementById('view-ev-name').textContent = event.name;
    document.getElementById('view-ev-meta').textContent = `${event.date || 'Date TBA'} · ${event.location || 'No venue'}`;
    document.getElementById('view-total').textContent     = guests.length;
    document.getElementById('view-checkedin').textContent = checkedIn;
    document.getElementById('view-pending').textContent   = guests.length - checkedIn;

    const listEl = document.getElementById('view-guest-list');
    if (!guests.length) {
      listEl.innerHTML = '<div style="padding:16px;font-size:0.78rem;color:var(--muted);">No guests added yet.</div>';
    } else {
      listEl.innerHTML = guests.map(g => {
        const chip = g.status === 'checked_in'
          ? '<span class="status-chip chip-in">Checked In</span>'
          : '<span class="status-chip chip-pending">Pending</span>';
        return `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);">
          <div>
            <div style="font-size:0.8rem;font-weight:600;">${g.name}</div>
            <div style="font-size:0.7rem;color:var(--muted);">${g.email}</div>
          </div>
          ${chip}
        </div>`;
      }).join('');
    }

   const viewModal = document.getElementById('view-modal');
    if (viewModal) viewModal.classList.add('open');

    if (typeof loadTeamAccessStatus === 'function') loadTeamAccessStatus(eventId);
  } catch(err) { 
    showToast('❌ Failed to load event details'); 
  }
}


function closeViewModal() {
  const modal = document.getElementById('view-modal');
  if (modal) modal.classList.remove('open');
}

// ── ACTION MODAL (Edit / Postpone / Cancel) ──
function editEvent(eventId) {
  closeViewModal();

  const modal = document.getElementById('action-modal');
  if (!modal) {
    console.error('action-modal not found');
    showToast('❌ Event action modal is missing');
    return;
  }

  actionEventId = parseInt(eventId, 10);
  backToChoice();
  modal.classList.add('open');
}

function closeActionModal() {
  const modal = document.getElementById('action-modal');
  if (modal) modal.classList.remove('open');
}

function backToChoice() {
  const choice = document.getElementById('action-choice');
  const postpone = document.getElementById('postpone-form');
  const cancel = document.getElementById('cancel-form');

  if (choice) choice.style.display = 'block';
  if (postpone) postpone.style.display = 'none';
  if (cancel) cancel.style.display = 'none';
}

function showPostponeForm() {
  const choice = document.getElementById('action-choice');
  const postpone = document.getElementById('postpone-form');
  if (choice) choice.style.display = 'none';
  if (postpone) postpone.style.display = 'block';
}

function showCancelForm() {
  const choice = document.getElementById('action-choice');
  const cancel = document.getElementById('cancel-form');
  if (choice) choice.style.display = 'none';
  if (cancel) cancel.style.display = 'block';
}

async function submitPostpone() {
  const reason = document.getElementById('postpone-reason').value.trim();
  const newDate = document.getElementById('postpone-date').value;
  const newTime = document.getElementById('postpone-time').value;
  const newVenue = document.getElementById('postpone-venue').value.trim();

  if (!reason || !newDate || !newTime || !newVenue) {
    showToast('⚠ Please fill all fields');
    return;
  }

  try {
    const res = await fetch(`/api/events/${actionEventId}/postpone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason, new_date: newDate, new_time: newTime, new_venue: newVenue })
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      showToast('❌ ' + (errorData.error || 'Failed to postpone event'));
      return;
    }

    const data = await res.json();
    showToast(`📅 Postponed — ${data.notified || 0} guest(s) notified with new QR`);
    closeActionModal();
    loadEventsTable();
    loadDashboardData();
  } catch (err) {
    console.error('submitPostpone error:', err);
    showToast('❌ Failed to postpone event');
  }
}

async function submitCancel() {
  const reason = document.getElementById('cancel-reason').value.trim();
  if (!reason) { showToast('⚠ Please provide a reason'); return; }
  if (!confirm('Are you sure? This cannot be undone.')) return;

  try {
    const res = await fetch(`/api/events/${actionEventId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    if (!res.ok) { showToast('❌ Failed to cancel event'); return; }
    const data = await res.json();
    showToast(`🚫 Event cancelled — ${data.notified} guest(s) notified`);
    closeActionModal();
    loadEventsTable();
    loadDashboardData();
  } catch(err) { showToast('❌ Failed to cancel event'); }
}