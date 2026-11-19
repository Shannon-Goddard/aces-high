(function () {
  const nav = document.getElementById('nav-root');
  if (!nav) return;

  // Detect root path depth for relative links
  const depth = (window.location.pathname.match(/\//g) || []).length - 1;
  const root  = depth > 1 ? '../' : './';

  const links = [
    { label: 'Predictions',   href: `${root}pages/predictions.html` },
    { label: 'Edge Report',   href: `${root}pages/edge-report.html` },
    { label: 'Teams',         href: `${root}pages/teams.html` },
    { label: 'Coaches',       href: `${root}pages/coaches.html` },
    { label: 'Players',       href: `${root}pages/players.html` },
    { label: 'Ledger',        href: `${root}pages/ledger.html` },
    { label: 'Stats',         href: `${root}pages/stats.html` },
    { label: 'Backtest',      href: `${root}pages/backtest.html` },
    { label: 'Findings',      href: `${root}pages/findings.html` },
    { label: 'Blog',          href: `${root}pages/blog.html` },
  ];

  const secondary = [
    { label: 'Methodology',   href: `${root}pages/methodology.html` },
    { label: 'About',         href: `${root}pages/about.html` },
    { label: 'Contact',       href: `${root}pages/contact.html` },
  ];

  const current = window.location.pathname.split('/').pop() || 'index.html';

  nav.innerHTML = `
    <div class="nav-overlay" id="nav-overlay"></div>
    <nav class="nav">
      <div class="nav-brand">
        <a href="${root}index.html" class="nav-logo">ACE'S HIGH</a>
        <span class="nav-tagline">He'd be workin' on this shit day and night.</span>
      </div>
      <button class="nav-toggle" id="nav-toggle" aria-label="Menu">&#9776;</button>
      <div class="nav-links" id="nav-links">
        <div class="nav-primary">
          ${links.map(l => `
            <a href="${l.href}"
               class="nav-link ${current === l.href.split('/').pop() ? 'active' : ''}"
               ${l.external ? 'target="_blank" rel="noopener"' : ''}>
              ${l.label}
            </a>`).join('')}
        </div>
        <div class="nav-secondary">
          ${secondary.map(l => `
            <a href="${l.href}"
               class="nav-link nav-link-sm"
               ${l.external ? 'target="_blank" rel="noopener"' : ''}>
              ${l.label}
            </a>`).join('')}
        </div>
      </div>
    </nav>
  `;

  const toggle  = document.getElementById('nav-toggle');
  const drawer   = document.getElementById('nav-links');
  const overlay  = document.getElementById('nav-overlay');

  function openMenu()  { drawer.classList.add('open'); overlay.classList.add('open'); }
  function closeMenu() { drawer.classList.remove('open'); overlay.classList.remove('open'); }

  toggle.addEventListener('click', () => drawer.classList.contains('open') ? closeMenu() : openMenu());
  overlay.addEventListener('click', closeMenu);
  drawer.querySelectorAll('.nav-link').forEach(l => l.addEventListener('click', closeMenu));

  // Back to top button
  const btn = document.createElement('a');
  btn.className = 'back-to-top';
  btn.href = '#';
  btn.setAttribute('aria-label', 'Back to top');
  btn.innerHTML = '&#8679;';
  btn.addEventListener('click', e => {
    e.preventDefault();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  document.body.appendChild(btn);

  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive: true });
})();
