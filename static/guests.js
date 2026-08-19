// ============================================================
// guests.js — guest list, inline check-in
// ADD NEW GUEST FEATURES HERE
// ============================================================

// ── EVENT SELECTION STATE ──
// The Guests tab now always scopes to one event at a time.
let selectedGuestEventId   = null;
let selectedGuestEventName = null;

// Called by the nav bar when the Guests tab is clicked.
function openGuestsTab() {

  // Make sure the event selector is closed
  const selector = document.getElementById('event-select-modal');

  if (selector) {
    selector.classList.remove('open');
  }

  if (selectedGuestEventId) {
    loadGuestsPage(selectedGuestEventId);
  } else {
    openEventSelector();
  }
}

// ── EVENT SELECT MODAL ──
async function openEventSelector() {

  const overlay =
    document.getElementById('event-select-modal');

  const list =
    document.getElementById('event-select-list');


  if (!overlay || !list) {

    console.error(
      'Guest event selector elements are missing.'
    );

    showToast(
      '❌ Event selector is not available'
    );

    return;

  }



  overlay.classList.add('open');

  overlay.style.zIndex = '2000';


  list.innerHTML =
    '<div style="padding:20px;font-size:0.78rem;color:var(--muted);">Loading events…</div>';


  try {

    const res =
      await fetch('/api/events');


    if (!res.ok) {

      throw new Error(
        'Failed to load events'
      );

    }


    const events =
      await res.json();


    if (!events.length) {

      list.innerHTML =
        '<div style="padding:20px;font-size:0.78rem;color:var(--muted);">No events yet — create one first.</div>';

      return;

    }


    list.innerHTML =
      events.map(e => {

        const safeName =
          String(e.name || '')
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'");


        return `

          <div
            class="guest-event-option"
            data-event-id="${e.id}"
            data-event-name="${safeName}"
            style="
              padding:12px 14px;
              background:rgba(255,255,255,0.03);
              border:1px solid rgba(255,255,255,0.07);
              border-radius:10px;
              cursor:pointer;
              display:flex;
              justify-content:space-between;
              align-items:center;
              transition:background 0.15s;
            "
          >

            <div>

              <div
                style="font-size:0.85rem;font-weight:600;"
              >
                ${e.name}
              </div>

              <div
                style="font-size:0.72rem;color:var(--muted);"
              >
                ${e.date || 'Date TBD'}
                ${e.location ? ' · ' + e.location : ''}
              </div>

            </div>

            <div
              style="font-size:0.72rem;color:var(--muted);"
            >
              ${e.status || 'active'}
            </div>

          </div>

        `;

      }).join('');


    // Attach click handlers AFTER creating the elements
    document
      .querySelectorAll('.guest-event-option')
      .forEach(option => {

        option.addEventListener(
          'click',
          function() {

            const id =
              parseInt(
                this.dataset.eventId,
                10
              );

            const name =
              this.dataset.eventName || '';


            selectGuestEvent(
              id,
              name
            );

          }
        );


        option.addEventListener(
          'mouseenter',
          function() {

            this.style.background =
              'rgba(74,124,255,0.08)';

          }
        );


        option.addEventListener(
          'mouseleave',
          function() {

            this.style.background =
              'rgba(255,255,255,0.03)';

          }
        );

      });


  }
  catch (err) {

    console.error(
      'openEventSelector error:',
      err
    );


    list.innerHTML =
      '<div style="padding:20px;font-size:0.78rem;color:var(--red);">Failed to load events.</div>';

  }

}

function closeEventSelectModal() {
  document.getElementById('event-select-modal').classList.remove('open');
}

function selectGuestEvent(id, name) {
  selectedGuestEventId   = id;
  selectedGuestEventName = name;
  closeEventSelectModal();
  const label = document.getElementById('guests-event-label');
  if (label) label.textContent = ' — ' + name;
  loadGuestsPage(id);
}

// ── LOAD GUESTS TABLE (scoped to one event) ──
async function loadGuestsPage(eventId) {
  const body = document.getElementById('guests-table-body');
  if (!body) return;

  // No event chosen yet — prompt instead of listing everyone.
 if (!eventId) {
    body.innerHTML = `<div style="padding:30px 20px;text-align:center;">
      <div style="font-size:0.85rem;margin-bottom:10px;color:var(--muted);">Select an event to view its guests.</div>
     <button
  type="button"
  class="btn-submit"
  id="guest-select-event-btn"
  onclick="openEventSelector()"
>
  Select event
</button>
    </div>`;
    return;
  }


  try {
    const res       = await fetch('/api/guests');
    const allGuests = await res.json();
    const guests    = allGuests.filter(g => g.event_id === eventId);

    if (!guests.length) {
      body.innerHTML = '<div style="padding:20px;font-size:0.78rem;color:var(--muted);">No guests for this event yet.</div>';
      return;
    }

    const avatarColors = [
      ['#3b5ff720','#6b9aff'], ['#7c3aed20','#a78bfa'],
      ['#05966920','#34d399'], ['#b4510720','#fb923c'],
      ['#0891b220','#22d3ee'], ['#dc262620','#f87171']
    ];

    body.innerHTML = guests.map((g, i) => {
      const initials   = (g.name || '??').split(' ').map(w => w[0]).join('').substring(0,2).toUpperCase();
      const c          = avatarColors[i % avatarColors.length];
      const isCheckedIn = g.status === 'checked_in';
      const chip       = isCheckedIn
        ? '<span class="status-chip chip-in">Checked In</span>'
        : '<span class="status-chip chip-pending">Pending</span>';
      const btn        = isCheckedIn
        ? '<button class="btn-sm ghost">View</button>'
        : `<button class="btn-sm primary" onclick="checkinGuest('${g.email}',${g.event_id},this)">Check In</button>`;

      return `<div class="gt-row">
        <div class="guest-cell">
          <div class="g-avatar" style="background:${c[0]};color:${c[1]};">${initials}</div>
          <div><div class="g-name">${g.name}</div><div class="g-email">${g.email}</div></div>
        </div>
        <div style="font-size:0.75rem;color:var(--muted)">${g.email}</div>
        <div style="font-size:0.75rem;">${g.event_name || '—'}</div>
        <div>${chip}</div>
        <div>${btn}</div>
      </div>`;
    }).join('');
  } catch(err) {
    body.innerHTML = '<div style="padding:20px;font-size:0.78rem;color:var(--red);">Failed to load guests.</div>';
  }
}

// ── INLINE CHECK-IN FROM GUESTS PAGE ──
async function checkinGuest(email, eventId, btn) {
  btn.disabled = true; btn.textContent = '…';
  try {
    const res  = await fetch('/api/checkin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, event_id: eventId })
    });
    const data = await res.json();
    if (data.success) {
      showToast('✅ ' + email + ' checked in!');
      loadGuestsPage(selectedGuestEventId);
      loadDashboardData();
    } else {
      btn.disabled = false; btn.textContent = 'Check In';
    }
  } catch(e) {
    btn.disabled = false; btn.textContent = 'Check In';
    showToast('❌ Server not reachable');
  }
}

// ── SEARCH FILTER ──
function filterGuests(q) {
  const rows = document.querySelectorAll('#guests-table-body .gt-row');
  rows.forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  });
}

// ── ALIASES (kept for backwards compatibility) ──
// Some HTML elements call these directly
async function loadGuests() { return loadGuestsPage(selectedGuestEventId); }
async function quickCheckin(email, eventId, btn) { return checkinGuest(email, eventId, btn); }