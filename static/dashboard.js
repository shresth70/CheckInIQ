// ============================================================
// dashboard.js — dashboard stats, chart, recent activity
// ADD NEW DASHBOARD WIDGETS HERE
// ============================================================

// ── STATS + RECENT ACTIVITY ──
async function loadDashboardData() {
  try {
    const res  = await fetch('/api/stats');
    const data = await res.json();

    // stat cards
    document.getElementById('stat-events').textContent    = data.total_events;
    document.getElementById('stat-guests').textContent    = data.total_guests.toLocaleString();
    document.getElementById('stat-checkedin').textContent = data.checked_in.toLocaleString();
    document.getElementById('stat-pending').textContent   = data.pending.toLocaleString();

    // percentage sub-labels
    const rate     = data.total_guests > 0 ? ((data.checked_in / data.total_guests) * 100).toFixed(1) : '0.0';
    const pendRate = data.total_guests > 0 ? ((data.pending    / data.total_guests) * 100).toFixed(1) : '0.0';
    const ciPctEl   = document.getElementById('stat-checkedin-pct');
    const pendPctEl = document.getElementById('stat-pending-pct');
    if (ciPctEl)   ciPctEl.textContent   = rate + '%';
    if (pendPctEl) pendPctEl.textContent = pendRate + '%';

    // recent check-in activity
    const actList = document.getElementById('activity-list');
    if (data.recent_checkins.length === 0) {
      actList.innerHTML = '<div style="font-size:0.75rem;color:var(--muted);padding:8px 0;">No check-ins yet</div>';
    } else {
      const colors = [
        ['#3b5ff720','#6b9aff'], ['#7c3aed20','#a78bfa'],
        ['#05966920','#34d399'], ['#b4510720','#fb923c']
      ];
      actList.innerHTML = data.recent_checkins.map((g, i) => {
        const initials = g.name.split(' ').map(w => w[0]).join('').substring(0,2).toUpperCase();
        const c = colors[i % colors.length];
        return `<div class="activity-item">
          <div class="avatar" style="background:${c[0]};color:${c[1]};">${initials}</div>
          <div class="activity-info">
            <div class="activity-name">${g.name}</div>
            <div class="activity-status">Checked in</div>
          </div>
        </div>`;
      }).join('');
    }

    // recent events
    const evtList = document.getElementById('recent-events-list');
    if (data.recent_events.length === 0) {
      evtList.innerHTML = '<div style="font-size:0.75rem;color:var(--muted);padding:8px 0;">No events yet — create one!</div>';
    } else {
      const icons = ['💡','📣','🎓','🎤','🏆'];
      evtList.innerHTML = data.recent_events.map((e, i) => `
        <div class="event-row">
          <div class="event-icon" style="background:rgba(74,124,255,0.15);">${icons[i % icons.length]}</div>
          <div class="event-info">
            <div class="event-name">${e.name}</div>
            <div class="event-date">${e.date || 'Date TBA'} · ${e.location || ''}</div>
          </div>
        </div>`).join('');
    }
  } catch(err) {
    console.error('loadDashboardData error:', err);
  }
}

// ── ATTENDANCE CHART ──
async function loadChart() {
  try {
    const res  = await fetch('/api/chart-data');
    const data = await res.json();

    if (data.length === 0) {
      document.getElementById('chart-line').setAttribute('d', 'M30,140 L490,140');
      document.getElementById('chart-area').setAttribute('d', 'M30,140 L490,140 L490,148 L30,148 Z');
      return;
    }

    const maxCount = Math.max(...data.map(d => d.count), 1);
    const w = 460, h = 130, startX = 30, startY = 140;
    const stepX = data.length > 1 ? w / (data.length - 1) : 0;

    const points = data.map((d, i) => ({
      x: startX + i * stepX,
      y: startY - (d.count / maxCount) * h,
      day: d.day,
      count: d.count
    }));

    let pathD = `M${points[0].x},${points[0].y}`;
    for (let i = 1; i < points.length; i++) pathD += ` L${points[i].x},${points[i].y}`;
    const areaD = pathD + ` L${points[points.length-1].x},148 L${points[0].x},148 Z`;

    document.getElementById('chart-line').setAttribute('d', pathD);
    document.getElementById('chart-area').setAttribute('d', areaD);
    window.chartPoints = points;

  } catch(err) { console.error('loadChart error:', err); }
}

// chart hover tooltip
document.getElementById('attendance-chart').addEventListener('mousemove', function(e) {
  if (!window.chartPoints || !window.chartPoints.length) return;
  const tip  = document.getElementById('chart-tip');
  const rect = this.getBoundingClientRect();
  const x    = e.clientX - rect.left;
  const idx  = Math.min(Math.floor((x / rect.width) * window.chartPoints.length), window.chartPoints.length - 1);
  const pt   = window.chartPoints[idx];
  tip.innerHTML = `<strong>${pt.day}</strong><br>Checked In: ${pt.count}`;
  tip.style.left = Math.min(x + 8, rect.width - 150) + 'px';
  tip.style.top  = '20px';
  tip.classList.add('show');
});
document.getElementById('attendance-chart').addEventListener('mouseleave', function() {
  document.getElementById('chart-tip').classList.remove('show');
});
