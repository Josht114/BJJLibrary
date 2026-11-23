"""Local BJJ Library server: serves the library pages and opens videos in VLC.

Start it with "Start BJJ Library.cmd" (or: pythonw server.py). It only listens on
127.0.0.1, so nothing outside this PC can reach it, and it stops by itself after
4 hours with no requests.
"""
import ctypes, html, http.server, json, os, re, socketserver, subprocess, sys, threading, time
from urllib.parse import quote

PORT = 8765
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VIDEO_EXT = {'.mp4', '.mkv', '.m4v', '.avi', '.flv', '.mov', '.webm', '.wmv'}
IDLE_SECONDS = 4 * 3600
VLC_PATHS = [os.path.join(os.environ.get(v, ''), 'VideoLAN', 'VLC', 'vlc.exe')
             for v in ('ProgramFiles', 'ProgramFiles(x86)')]
ALLOWED_HOSTS = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
REPORTS_DIR = os.path.join(HERE, 'reports')
MAX_REPORT_BYTES = 10 * 1024 * 1024


def list_reports():
    """Saved reports, newest first: [{name, url, title, saved, bytes}]"""
    out = []
    if os.path.isdir(REPORTS_DIR):
        for f in os.listdir(REPORTS_DIR):
            if not f.lower().endswith('.html'):
                continue
            p = os.path.join(REPORTS_DIR, f)
            title = f.rsplit('_', 2)[0].replace('-', ' ')
            try:
                with open(p, encoding='utf-8') as fh:
                    m = re.search(r'<title>(.*?)</title>', fh.read(4000), re.S)
                if m:
                    title = html.unescape(m.group(1)).strip()
            except OSError:
                pass
            st = os.stat(p)
            out.append({'name': f, 'url': '/_BJJ%20Library/reports/' + quote(f), 'title': title,
                        'saved': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(st.st_mtime)), 'bytes': st.st_size,
                        'file': p})
    return sorted(out, key=lambda r: r['saved'], reverse=True)
last_request = time.time()


def log(msg):
    try:
        with open(os.path.join(HERE, 'server.log'), 'a', encoding='utf-8') as fh:
            fh.write(time.strftime('%Y-%m-%dT%H:%M:%S  ') + msg + '\n')
    except OSError:
        pass


def resolve(rel):
    """Library-relative path -> absolute path, only if it is an existing video or folder inside ROOT."""
    full = os.path.realpath(os.path.join(ROOT, *rel.replace('\\', '/').split('/')))
    if not full.lower().startswith(os.path.realpath(ROOT).lower() + os.sep):
        return None, 'outside the library folder'
    if os.path.isdir(full):
        return full, None
    if not os.path.isfile(full):
        return None, 'file not found'
    if os.path.splitext(full)[1].lower() not in VIDEO_EXT:
        return None, 'not a video file'
    return full, None


def bring_vlc_to_front():
    """Windows keeps newly launched apps behind the browser; pull VLC forward."""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if buf.value.endswith('VLC media player'):
                found.append(hwnd)
        return True

    for _ in range(32):  # wait up to 8s for the window
        time.sleep(0.25)
        found.clear()
        user32.EnumWindows(cb, 0)
        if found:
            break
    if not found:
        return False
    hwnd = found[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)  # Alt tap lets this process change the foreground window
    user32.keybd_event(0x12, 0, 2, 0)
    return bool(user32.SetForegroundWindow(hwnd))


def open_in_player(full):
    if os.path.isdir(full):
        subprocess.Popen(['explorer.exe', full])
        return 'folder'
    vlc = next((p for p in VLC_PATHS if os.path.isfile(p)), None)
    if vlc:
        subprocess.Popen([vlc, '--one-instance', full])
        threading.Thread(target=bring_vlc_to_front, daemon=True).start()
        return 'vlc'
    os.startfile(full)
    return 'default app'


class Handler(http.server.SimpleHTTPRequestHandler):
    # Keep-alive connections: closing the socket after every file occasionally made Windows
    # reset the connection mid-download (seen as ERR_CONNECTION_RESET on data.js).
    protocol_version = 'HTTP/1.1'

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # Always revalidate, so rebuilt pages/data (and nav.js) show up without a hard refresh
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        return self.headers.get('Host', '') in ALLOWED_HOSTS  # blocks DNS-rebinding tricks

    def do_GET(self):
        global last_request
        last_request = time.time()
        if not self._host_ok():
            return self._json(403, {'error': 'bad host'})
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/_BJJ%20Library/index.html')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if self.path == '/api/ping':
            return self._json(200, {'ok': True})
        if self.path == '/api/reports':
            return self._json(200, {'reports': list_reports()})
        return super().do_GET()

    def do_POST(self):
        global last_request
        last_request = time.time()
        # Only our own pages may call the API: same host, same origin, and a custom header
        # (other websites can't send a custom header to localhost without a CORS preflight we never allow).
        origin = self.headers.get('Origin', '')
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            n = -1
        if n < 0 or n > MAX_REPORT_BYTES:
            self.close_connection = True  # don't leave an unread body on a kept-alive connection
            return self._json(413, {'error': 'request too large'})
        body = self.rfile.read(n) if n else b''
        if (not self._host_ok() or self.path not in ('/api/open', '/api/save-report') or self.headers.get('X-BJJ') != '1'
                or origin not in {f'http://{h}' for h in ALLOWED_HOSTS}):
            log(f'refused request: path={self.path} origin={origin!r}')
            return self._json(403, {'error': 'forbidden'})
        try:
            data = json.loads(body or b'{}')
        except json.JSONDecodeError:
            return self._json(400, {'error': 'bad request'})
        if self.path == '/api/save-report':
            return self._save_report(data)
        rel = data.get('path', '')
        if not isinstance(rel, str):
            return self._json(400, {'error': 'bad request'})
        full, err = resolve(rel)
        if err:
            log(f'refused {rel!r}: {err}')
            return self._json(400, {'error': err})
        how = open_in_player(full)
        log(f'opened ({how}): {full}')
        return self._json(200, {'ok': True, 'opened': how})

    def _save_report(self, data):
        """Write a generated report to _BJJ Library/reports/<title>_<timestamp>.html (never overwrites)."""
        title, page = data.get('title', ''), data.get('html', '')
        if not isinstance(title, str) or not isinstance(page, str) or not page.lstrip().lower().startswith('<!doctype html>'):
            return self._json(400, {'error': 'bad report'})
        slug = re.sub(r'[^A-Za-z0-9]+', '-', title).strip('-')[:60] or 'report'
        os.makedirs(REPORTS_DIR, exist_ok=True)
        name = f'{slug}_{time.strftime("%Y-%m-%d_%H%M%S")}.html'
        path = os.path.join(REPORTS_DIR, name)
        with open(path, 'x', encoding='utf-8') as fh:
            fh.write(page)
        log(f'saved report: {path}')
        return self._json(200, {'ok': True, 'file': path, 'url': '/_BJJ%20Library/reports/' + quote(name)})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def idle_watch(srv):
    while True:
        time.sleep(60)
        if time.time() - last_request > IDLE_SECONDS:
            log('idle for 4h, stopping')
            srv.shutdown()
            return


def main():
    try:
        srv = Server(('127.0.0.1', PORT), Handler)
    except OSError:
        print(f'Already running on http://127.0.0.1:{PORT}/')
        return
    log(f'started on http://127.0.0.1:{PORT}/')
    threading.Thread(target=idle_watch, args=(srv,), daemon=True).start()
    srv.serve_forever()


if __name__ == '__main__':
    main()
