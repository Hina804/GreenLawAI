/* ============================================================
   GREENLAW AI · HAZARA FOREST INTELLIGENCE · v4.0
   Shared JavaScript — Navigation, Clock, Animations
   ============================================================ */

'use strict';

// ── Clock ──────────────────────────────────────────────────
function updateClock() {
  const clocks = document.querySelectorAll('.topbar-clock');
  const now = new Date();
  const pkt = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Karachi' }));
  const pad = n => String(n).padStart(2, '0');
  const str = `PKT ${pad(pkt.getHours())}:${pad(pkt.getMinutes())}:${pad(pkt.getSeconds())}`;
  clocks.forEach(c => c.textContent = str);
}
setInterval(updateClock, 1000);
updateClock();

// ── Mobile sidebar toggle ──────────────────────────────────
const sidebar  = document.querySelector('.sidebar');
const overlay  = document.querySelector('.sidebar-overlay');
const menuBtn  = document.querySelector('.menu-toggle');

if (menuBtn) {
  menuBtn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('visible');
  });
}
if (overlay) {
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('visible');
  });
}

// ── Active nav link ────────────────────────────────────────
(function setActiveNav() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-item a').forEach(link => {
    const href = link.getAttribute('href');
    if (href === page || (page === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });
})();

// ── Counter animation ──────────────────────────────────────
function animateCounters() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target = parseFloat(el.dataset.target);
    const suffix = el.dataset.suffix || '';
    const prefix = el.dataset.prefix || '';
    const duration = 1200;
    const start = performance.now();
    const isFloat = String(target).includes('.');

    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = isFloat
        ? (eased * target).toFixed(1)
        : Math.floor(eased * target).toLocaleString();
      el.textContent = prefix + current + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

// Run counters on load
window.addEventListener('load', () => {
  setTimeout(animateCounters, 200);
});

// ── Stagger card reveal ────────────────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      entry.target.style.animationDelay = `${i * 60}ms`;
      entry.target.classList.add('revealed');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.05 });

document.querySelectorAll('.kpi-card, .card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(12px)';
  el.style.transition = 'opacity .4s ease, transform .4s ease';
  observer.observe(el);
});

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.kpi-card, .card').forEach(el => {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });
  }, 50);
});

// ── Simulate live alert ticker ─────────────────────────────
const liveAlerts = [
  { type: 'critical', icon: '🔥', title: 'Fire Detected', loc: 'Mansehra Block-7', time: 'Just now' },
  { type: 'high',     icon: '🌲', title: 'Deforestation Activity', loc: 'Abbottabad Sector 3', time: '3 min' },
  { type: 'medium',   icon: '⚠️', title: 'Patrol Overdue', loc: 'Battagram Zone 2', time: '8 min' },
  { type: 'info',     icon: 'ℹ️', title: 'Citizen Report', loc: 'Haripur District', time: '14 min' },
];

// ── Tooltip helper ─────────────────────────────────────────
document.querySelectorAll('[data-tooltip]').forEach(el => {
  el.addEventListener('mouseenter', function(e) {
    const tip = document.createElement('div');
    tip.className = 'tooltip-popup';
    tip.textContent = this.dataset.tooltip;
    tip.style.cssText = `
      position:fixed;background:#1e293b;color:#fff;
      font-size:11px;padding:5px 10px;border-radius:6px;
      pointer-events:none;z-index:9999;white-space:nowrap;
      box-shadow:0 2px 8px rgba(0,0,0,.2);
    `;
    document.body.appendChild(tip);
    const rect = this.getBoundingClientRect();
    tip.style.top  = (rect.top - tip.offsetHeight - 6) + 'px';
    tip.style.left = (rect.left + rect.width/2 - tip.offsetWidth/2) + 'px';
    this._tip = tip;
  });
  el.addEventListener('mouseleave', function() {
    if (this._tip) { this._tip.remove(); this._tip = null; }
  });
});

// ── Chart default config ───────────────────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#64748b';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = { size: 12, weight: '700' };
  Chart.defaults.plugins.tooltip.bodyFont  = { size: 12 };
}
