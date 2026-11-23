// Shared top bar linking the BJJ Library pages. Include right after <body>:  <script src="nav.js"></script>
(function () {
  const pages = [
    ['index.html', 'Library'],
    ['my-game.html', 'Study guide'],
    ['report.html', 'Report builder'],
    ['saved-reports.html', 'Saved reports'],
    ['wiki.html', 'Wiki'],
  ];
  // A saved report (in /reports/) highlights the Saved reports tab
  const here = /\/reports\/[^/]+$/.test(decodeURIComponent(location.pathname)) ? 'saved-reports.html'
    : (location.pathname.split('/').pop() || 'index.html').toLowerCase();

  const css = `
  :root { --bjjnav-bg:#1d1d1f; --bjjnav-ink:#f2f2f4; --bjjnav-muted:#a8a8b0; --bjjnav-on:#ffffff; --bjjnav-on-bg:#2f5bd3; --bjjnav-hover:#2c2c31; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bjjnav-bg:#0b0b0d; --bjjnav-on-bg:#7b9cff; --bjjnav-on:#0d0d10; --bjjnav-hover:#1f1f24; } }
  :root[data-theme="dark"] { --bjjnav-bg:#0b0b0d; --bjjnav-on-bg:#7b9cff; --bjjnav-on:#0d0d10; --bjjnav-hover:#1f1f24; }
  #bjjnav { position:sticky; top:0; z-index:50; display:flex; align-items:center; gap:16px; height:48px; padding:0 16px;
    background:var(--bjjnav-bg); color:var(--bjjnav-ink); font:14px/1 system-ui,-apple-system,"Segoe UI",sans-serif;
    border-bottom:1px solid rgba(255,255,255,.08); }
  #bjjnav .brand { font-weight:700; font-size:15px; letter-spacing:.01em; white-space:nowrap; color:var(--bjjnav-ink); text-decoration:none; }
  #bjjnav .brand span { color:var(--bjjnav-muted); font-weight:500; }
  #bjjnav nav { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; min-width:0; }
  #bjjnav nav::-webkit-scrollbar { display:none; }
  #bjjnav a.tab { color:var(--bjjnav-muted); text-decoration:none; padding:8px 12px; border-radius:7px; white-space:nowrap; font-weight:500; }
  #bjjnav a.tab:hover { background:var(--bjjnav-hover); color:var(--bjjnav-ink); }
  #bjjnav a.tab.on { background:var(--bjjnav-on-bg); color:var(--bjjnav-on); }
  @media (max-width:600px) { #bjjnav .brand span { display:none; } #bjjnav { gap:10px; } #bjjnav a.tab { padding:8px 9px; } }
  @media print { #bjjnav { display:none; } }`;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  const bar = document.createElement('header');
  bar.id = 'bjjnav';
  bar.innerHTML = `<a class="brand" href="index.html">🥋 BJJ <span>Library</span></a><nav>` +
    pages.map(([href, label]) => `<a class="tab${href === here ? ' on' : ''}" href="${href}"${href === here ? ' aria-current="page"' : ''}>${label}</a>`).join('') +
    `</nav>`;
  document.body.insertBefore(bar, document.body.firstChild);

  // On narrow screens the tabs scroll sideways: make sure the current page's tab is visible
  const tabs = bar.querySelector('nav'), cur = bar.querySelector('a.on');
  if (cur && tabs.scrollWidth > tabs.clientWidth) tabs.scrollLeft = cur.offsetLeft - tabs.offsetLeft - 8;

  // Pages use --navh to keep their sticky sidebars / headers below the bar
  const setH = () => document.documentElement.style.setProperty('--navh', bar.offsetHeight + 'px');
  setH();
  window.addEventListener('resize', setH);
})();
