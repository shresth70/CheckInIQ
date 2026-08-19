// ============================================================
// core.js — auth, navigation, toast, shared utilities
// ADD NEW SHARED FUNCTIONS HERE
// ============================================================

// ----- AUTH GUARD -----
let currentUser = null;

async function checkAuth() {
  try {
    const res = await fetch('/api/me', { credentials: 'same-origin' });
    if (!res.ok) { window.location.href = '/'; return null; }
    currentUser = await res.json();
    return currentUser;
  } catch (err) {
    window.location.href = '/';
    return null;
  }
}

async function handleLogout() {
  try {
    await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
  } finally {
    window.location.href = '/';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const user = await checkAuth();
  if (!user) return;

  const nameEl = document.getElementById('user-name');
  if (nameEl) nameEl.textContent = user.name;

  loadDashboardData();
  loadChart();
  loadCheckinsPage();
  loadGuestsPage(selectedGuestEventId);
  loadEventsTable();
});

//function handleLogout() {
  //localStorage.removeItem('checkiniq_user');
  //window.location.href = '/';
//}

// ----- NAVIGATION -----
function navigate(el) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.main').forEach(m => m.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-' + el.dataset.page).classList.add('active');
  // call the right loader per page
  if (el.dataset.page === 'guests')   openGuestsTab();
  if (el.dataset.page === 'events')   loadEventsTable();
  if (el.dataset.page === 'checkins') loadCheckinsPage();
}

// ----- TOAST -----
let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

// ----- KEYBOARD SHORTCUTS -----
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeModal();
    closeViewModal();
    closeActionModal();
  }
});

// ----- INIT: load everything on page load -----

// ---- dark/light------
function toggleTheme() {
  const root   = document.documentElement;
  const btn    = document.getElementById('theme-toggle');
  const isLight = root.getAttribute('data-theme') === 'light';

  if (isLight) {
    root.removeAttribute('data-theme');
    btn.textContent = '☀️ Light';
    localStorage.setItem('checkiniq_theme', 'dark');
  } else {
    root.setAttribute('data-theme', 'light');
    btn.textContent = '🌙 Dark';
    localStorage.setItem('checkiniq_theme', 'light');
  }
}

// apply saved theme on load
const savedTheme = localStorage.getItem('checkiniq_theme');
if (savedTheme === 'light') {
  document.documentElement.setAttribute('data-theme', 'light');
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = '🌙 Dark';
  });
}