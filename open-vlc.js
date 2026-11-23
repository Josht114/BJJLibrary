// "Open in VLC" buttons: any element with data-open="<path relative to the VIDEOS folder>".
// Needs the local server (Start BJJ Library.cmd); pages opened straight from disk can't launch VLC.
(function () {
  function toast(msg, bad) {
    let t = document.getElementById('vlc-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'vlc-toast';
      t.style.cssText = 'position:fixed;left:50%;bottom:20px;transform:translateX(-50%);max-width:min(560px,calc(100vw - 32px));' +
        'padding:10px 16px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;z-index:99;box-shadow:0 4px 16px rgba(0,0,0,.25)';
      document.body.appendChild(t);
    }
    t.style.background = bad ? '#b3261e' : '#1d6b46';
    t.style.color = '#fff';
    t.textContent = msg;
    t.style.display = 'block';
    clearTimeout(t._h);
    t._h = setTimeout(() => { t.style.display = 'none'; }, bad ? 7000 : 2500);
  }

  document.addEventListener('click', async ev => {
    const b = ev.target.closest('[data-open]');
    if (!b) return;
    ev.preventDefault();
    if (location.protocol !== 'http:') {
      toast('To open videos in VLC, start the library with "Start BJJ Library" in the _BJJ Library folder.', true);
      return;
    }
    const label = b.textContent;
    b.textContent = 'Opening…';
    try {
      const r = await fetch('/api/open', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BJJ': '1' },
        body: JSON.stringify({ path: b.dataset.open }),
      });
      const j = await r.json();
      if (r.ok) toast(j.opened === 'folder' ? 'Opened the folder' : 'Opening in VLC…');
      else toast('Could not open: ' + (j.error || r.status), true);
    } catch (e) {
      toast('The BJJ Library server isn\'t running. Double-click "Start BJJ Library" in the _BJJ Library folder.', true);
    } finally {
      b.textContent = label;
    }
  });
})();
