/* ============================================================
   GREENLAW AI — Shared Navigation Renderer
   ============================================================ */

(function renderNav() {
  const navHTML = `
    <nav class="sidebar" id="sidebar">
      <a class="sidebar-brand" href="index.html">
        <div class="brand-icon">🌲</div>
        <div class="brand-text">
          <div class="brand-name">GREENLAW AI</div>
          <div class="brand-tagline">HAZARA OPS</div>
        </div>
      </a>

      <div class="sidebar-section-label">Intelligence</div>
      <ul class="nav-list">
        <li class="nav-item">
          <a href="index.html">
            <span class="nav-icon"><i class="fa fa-tachometer-alt"></i></span>
            Dashboard
            <span class="nav-badge">3</span>
          </a>
        </li>
        <li class="nav-item">
          <a href="chat.html">
            <span class="nav-icon"><i class="fa fa-robot"></i></span>
            AI Chat
          </a>
        </li>
      </ul>

      <div class="sidebar-section-label">Legal</div>
      <ul class="nav-list">
        <li class="nav-item">
          <a href="legal.html">
            <span class="nav-icon"><i class="fa fa-balance-scale"></i></span>
            Legal Analysis
          </a>
        </li>
        <li class="nav-item">
          <a href="judiciary.html">
            <span class="nav-icon"><i class="fa fa-gavel"></i></span>
            Judiciary
            <span class="nav-badge amber">47</span>
          </a>
        </li>
      </ul>

      <div class="sidebar-section-label">Operations</div>
      <ul class="nav-list">
        <li class="nav-item">
          <a href="monitoring.html">
            <span class="nav-icon"><i class="fa fa-satellite-dish"></i></span>
            Monitoring
            <span class="nav-badge">23</span>
          </a>
        </li>
        <li class="nav-item">
          <a href="predict.html">
            <span class="nav-icon"><i class="fa fa-chart-line"></i></span>
            Predict
          </a>
        </li>
        <li class="nav-item">
          <a href="operations.html">
            <span class="nav-icon"><i class="fa fa-binoculars"></i></span>
            Operations
          </a>
        </li>
      </ul>

      <div class="sidebar-section-label">Public</div>
      <ul class="nav-list">
        <li class="nav-item">
          <a href="citizen.html">
            <span class="nav-icon"><i class="fa fa-users"></i></span>
            Citizen Reports
            <span class="nav-badge green">8</span>
          </a>
        </li>
        <li class="nav-item">
          <a href="permit.html">
            <span class="nav-icon"><i class="fa fa-file-certificate"></i></span>
            Permits
          </a>
        </li>
      </ul>

      <div class="sidebar-footer">
        <div class="sys-status">
          <span class="status-dot"></span>
          ALL SYSTEMS OPERATIONAL
        </div>
        <div class="sidebar-version">v4.0.1 · PKT Zone</div>
      </div>
    </nav>
    <div class="sidebar-overlay" id="sidebarOverlay"></div>
  `;

  const container = document.getElementById('nav-container');
  if (container) container.innerHTML = navHTML;
})();
