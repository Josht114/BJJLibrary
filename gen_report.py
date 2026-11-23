"""Generate my-game.html: study references for every move in my_game.py.

Run after build.py:  python gen_report.py
"""
import html, json, os, re, sys, collections
from urllib.parse import quote
from my_game import GAME

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = {
    'ch': ('Chapter', 'Chapter title names the move'),
    'ts': ('Timestamp', 'From the course contents file'),
    'vol': ('Volume', "The publisher's chapter list names it in this volume"),
    'likely': ('Likely', 'Chapter/volume title strongly suggests it'),
    'course': ('Course', 'Course covers it; chapter not labelled'),
}
STRONG = {'ch', 'ts', 'vol'}


def load():
    src = open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()
    return json.loads(src[src.index('=') + 1:].strip().rstrip(';'))


def href(rel):
    return '../' + '/'.join(quote(p) for p in rel.split('/'))


def video_label(f):
    b = f.split('/')[-1]
    return re.sub(r'\.(mp4|mkv|m4v|avi|flv|mov)(\.mp4|\.mov)?$', '', b, flags=re.I)


ROOT = os.path.dirname(HERE)


def winpath(rel):
    """Full Windows path for a library-relative path."""
    return os.path.join(ROOT, *rel.split('/'))


def fmt_dur(s):
    """Seconds -> '7:05' or '1h 02m'."""
    if not s:
        return ''
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f'{h}h {m:02d}m' if h else f'{m}:{sec:02d}'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def main():
    lib = load()
    courses = lib['courses']
    e = html.escape
    usage = collections.Counter()
    gaps, strong_moves, total_moves = [], 0, 0
    sections = []
    pos_names = [p for p, _ in GAME]
    by_course = {c['path']: i for i, c in enumerate(courses)}
    by_video = {v['f']: (i, j) for i, c in enumerate(courses) for j, v in enumerate(c['videos'])}

    def resolve(ref):
        """Ref is a video path or a course folder path -> (course index, video index or None)."""
        if ref in by_video:
            return by_video[ref]
        if ref in by_course:
            return by_course[ref], None
        sys.exit(f'my_game.py reference not found in library (moved or renamed?): {ref}')

    export = []  # game.js, used by report.html
    for pos, moves in GAME:
        rows = []
        ex_moves = []
        for name, dest, refs in moves:
            ex_refs = []
            total_moves += 1
            if any(k in STRONG for _, k, _ in refs):
                strong_moves += 1
            elif not any(k == 'likely' for _, k, _ in refs):
                gaps.append((pos, name))
            items = []
            resolved = [resolve(ref) for ref, _, _ in refs]
            for c_i in {ci for ci, _ in resolved}:
                usage[c_i] += 1
            for (ref, kind, note), (ci, vi) in zip(refs, resolved):
                c = courses[ci]
                gi = {'gi': 'Gi', 'nogi': 'No-Gi', 'both': 'Gi/No-Gi'}.get(c['g'], '')
                if vi is not None:
                    v = c['videos'][vi]
                    target = href(v['f'])
                    what = f'<span class="vid">▶ {e(video_label(v["f"]))}</span>'
                    dur = fmt_dur(v.get('d'))
                    loc = winpath(v['f'])
                    vlc = v['f']
                else:
                    target = href(c['videos'][0]['f']) if c['videos'] else href(c['path'])
                    what = f'<span class="vid">▶ Start at video 1 of {len(c["videos"])}</span>'
                    total = sum(v.get('d') or 0 for v in c['videos'])
                    dur = ('whole course ' + fmt_dur(total) + ('+' if any(not v.get('d') for v in c['videos']) else '')) if total else ''
                    loc = winpath(c['path']) + '\\'
                    vlc = c['videos'][0]['f'] if c['videos'] else c['path']
                ex_refs.append({'kind': kind, 'note': note, 'course': c['t'], 'inst': c['i'], 'gi': gi,
                                'video': video_label(v['f']) if vi is not None else None,
                                'nvideos': len(c['videos']), 'open': vlc, 'href': target, 'loc': loc,
                                'd': (v.get('d') if vi is not None else None),
                                'total': (total if vi is None else None), 'ci': ci})
                label, tip = KIND[kind]
                items.append(
                    f'<li><span class="k k-{kind}" title="{e(tip)}">{label}</span>'
                    f'<div class="ref"><a href="{target}" target="_blank">{what}</a>'
                    f'{f" <span class=dur>{dur}</span>" if dur else ""}'
                    f'<div class="src"><b>{e(c["t"])}</b>{" · " + e(c["i"]) if c["i"] else ""}'
                    f'{f" · <span class=g>{gi}</span>" if gi else ""}</div>'
                    f'<div class="note">{e(note)}</div>'
                    f'<div class="loc"><code title="Click to select, then Ctrl+C">{e(loc)}</code>'
                    f'<button class="vlc" data-open="{e(vlc)}" title="Open from F: in VLC (no download)">Open in VLC</button>'
                    f'<button class="cp" data-p="{e(loc)}">Copy</button></div></div></li>')
            arrow = (f'<a class="dest" href="#{slug(dest)}">→ {e(dest)}</a>'
                     if dest and dest in pos_names else (f'<span class="dest">→ {e(dest)}</span>' if dest else '<span class="sub">Submission</span>'))
            ex_moves.append({'name': name, 'dest': dest, 'refs': ex_refs})
            rows.append(f'<details class="move" open><summary><h3>{e(name)} {arrow}'
                        f'<span class="picks">{len(refs)} picks</span></h3></summary><ul>{"".join(items)}</ul></details>')
        top = 'top' if pos.lower().startswith('top') or pos == 'Standing' else 'bottom'
        names = ' · '.join(e(m[0]) for m in moves)
        export.append({'pos': pos, 'id': slug(pos), 'side': top, 'moves': ex_moves})
        sections.append(f'<details class="pos {top}" id="{slug(pos)}"><summary><h2>{e(pos)}</h2>'
                        f'<span class="count">{len(moves)} moves</span><span class="names">{names}</span></summary>'
                        f'{"".join(rows)}</details>')

    top_courses = ''.join(
        f'<li><b>{e(courses[ci]["t"])}</b> <span class="muted">{e(courses[ci]["i"])}</span> <span class="cnt">{n} moves</span></li>'
        for ci, n in usage.most_common(10))
    gap_list = ''.join(f'<li><a href="#{slug(p)}">{e(m)}</a> <span class="muted">({e(p)})</span></li>' for p, m in gaps)
    toc_top = ''.join(f'<a href="#{slug(p)}">{e(p)}</a>' for p in pos_names if p.startswith('Top') or p == 'Standing')
    toc_bot = ''.join(f'<a href="#{slug(p)}">{e(p)}</a>' for p in pos_names if p.startswith('Bottom'))

    page = TEMPLATE.format(
        moves=total_moves, strong=strong_moves, gaps_n=len(gaps), positions=len(GAME),
        top_courses=top_courses, gap_list=gap_list or '<li>None</li>',
        toc_top=toc_top, toc_bot=toc_bot, sections=''.join(sections))
    with open(os.path.join(HERE, 'game.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.GAME = ' + json.dumps(export, ensure_ascii=False) + ';' + chr(10))
    out = os.path.join(HERE, 'my-game.html')
    open(out, 'w', encoding='utf-8').write(page)
    print(f'Wrote {out}: {total_moves} moves, {strong_moves} with chapter/timestamp refs, {len(gaps)} course-only')


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Game Study Guide</title>
<style>
:root {{ --bg:#f6f5f2; --panel:#fff; --ink:#1d1d1f; --muted:#6b6b70; --line:#e4e2dd; --accent:#2f5bd3;
  --top:#2f5bd3; --bot:#b4542b; --ch:#1d6b46; --ch-bg:#dcf1e5; --ts:#5a3fb0; --ts-bg:#e9e2fb; --lk:#8a5a00; --lk-bg:#fbefd6; --co:#55555a; --co-bg:#eeece7; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#141416; --panel:#1d1d20; --ink:#ececee; --muted:#9a9aa2; --line:#2e2e33; --accent:#7b9cff;
  --top:#7b9cff; --bot:#f0936a; --ch:#7fd8a6; --ch-bg:#15342a; --ts:#bba8ff; --ts-bg:#2c2346; --lk:#f2c46b; --lk-bg:#3a2d12; --co:#b5b5bb; --co-bg:#2a2a2f; }} }}
:root[data-theme="dark"] {{ --bg:#141416; --panel:#1d1d20; --ink:#ececee; --muted:#9a9aa2; --line:#2e2e33; --accent:#7b9cff;
  --top:#7b9cff; --bot:#f0936a; --ch:#7fd8a6; --ch-bg:#15342a; --ts:#bba8ff; --ts-bg:#2c2346; --lk:#f2c46b; --lk-bg:#3a2d12; --co:#b5b5bb; --co-bg:#2a2a2f; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:1000px; margin:0 auto; padding:28px 16px 80px; }}
h1 {{ font-size:30px; margin:0 0 4px; }}
.lede {{ color:var(--muted); margin:0 0 20px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:18px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.stat b {{ display:block; font-size:24px; }} .stat span {{ color:var(--muted); font-size:13px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:18px; }}
.box {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.box h2 {{ font-size:15px; margin:0 0 8px; }} .box ol, .box ul {{ margin:0; padding-left:20px; }} .box li {{ margin:3px 0; }}
.cnt {{ font-size:12px; color:var(--muted); white-space:nowrap; }} .muted {{ color:var(--muted); font-size:13px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px 16px; font-size:13px; color:var(--muted); margin:0 0 16px; }}
nav.toc {{ position:sticky; top:var(--navh,0px); z-index:2; background:var(--bg); padding:10px 0; border-bottom:1px solid var(--line); margin-bottom:10px; }}
nav.toc div {{ display:flex; flex-wrap:wrap; gap:6px; margin:3px 0; }}
nav.toc a {{ font-size:12px; text-decoration:none; padding:2px 9px; border-radius:99px; background:var(--panel); border:1px solid var(--line); color:var(--ink); }}
nav.toc .lbl {{ font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); align-self:center; width:56px; }}
details.pos {{ margin-top:10px; scroll-margin-top:150px; border:1px solid var(--line); border-left:4px solid var(--top); border-radius:10px; background:var(--panel); }}
details.pos.bottom {{ border-left-color:var(--bot); }}
details.pos > summary {{ list-style:none; cursor:pointer; padding:12px 16px 12px 40px; position:relative; display:flex; flex-wrap:wrap; align-items:baseline; gap:2px 12px; }}
details.pos > summary::-webkit-details-marker, details.move > summary::-webkit-details-marker {{ display:none; }}
details.pos > summary::before, details.move > summary::before {{ content:"›"; position:absolute; left:16px; top:9px; font-size:22px; line-height:1; color:var(--muted); transition:transform .15s; }}
details[open] > summary::before {{ transform:rotate(90deg); }}
details.pos > summary h2 {{ font-size:19px; margin:0; }}
details.pos > summary .count {{ font-size:13px; font-weight:600; color:var(--muted); }}
details.pos > summary .names {{ flex-basis:100%; font-size:13px; color:var(--muted); }}
details.pos[open] > summary .names {{ display:none; }}
details.pos[open] > summary {{ border-bottom:1px solid var(--line); }}
details.pos > .move:first-of-type {{ margin-top:12px; }}
.move {{ background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:10px 16px; margin:0 12px 10px; }}
details.move > summary {{ list-style:none; cursor:pointer; position:relative; padding-left:22px; }}
details.move > summary::before {{ left:0; top:-3px; font-size:20px; }}
details.move[open] > summary {{ margin-bottom:6px; }}
.move h3 {{ margin:0; font-size:16px; display:flex; flex-wrap:wrap; gap:4px 10px; align-items:baseline; }}
.picks {{ font-size:12px; font-weight:500; color:var(--muted); }}
.tools {{ display:flex; gap:6px; margin:6px 0 2px; }}
.tools button {{ font:inherit; font-size:12px; padding:3px 10px; border-radius:6px; border:1px solid var(--line); background:var(--panel); color:var(--ink); cursor:pointer; }}
.tools button:hover {{ border-color:var(--accent); color:var(--accent); }}
.dest {{ font-size:13px; font-weight:500; color:var(--accent); text-decoration:none; }}
.sub {{ font-size:12px; font-weight:500; color:var(--muted); }}
.move ul {{ list-style:none; margin:0; padding:0; }}
.move li {{ display:flex; gap:10px; padding:7px 0; border-top:1px solid var(--line); }}
.move li:first-child {{ border-top:0; }}
.k {{ flex:0 0 76px; text-align:center; font-size:11px; font-weight:600; border-radius:99px; padding:2px 0; height:fit-content; margin-top:2px; }}
.k-ch {{ background:var(--ch-bg); color:var(--ch); }} .k-ts {{ background:var(--ts-bg); color:var(--ts); }}
.k-vol {{ background:var(--ts-bg); color:var(--ts); }} .k-likely {{ background:var(--lk-bg); color:var(--lk); }} .k-course {{ background:var(--co-bg); color:var(--co); }}
.ref {{ min-width:0; }} .ref a {{ color:var(--ink); text-decoration:none; font-weight:600; overflow-wrap:anywhere; }}
.ref a:hover {{ color:var(--accent); }}
.src {{ font-size:13px; color:var(--muted); }} .src b {{ color:var(--ink); font-weight:500; }}
.g {{ font-size:12px; }} .note {{ font-size:13px; }}
.dur {{ font-size:12px; font-weight:600; color:var(--muted); background:var(--bg); border:1px solid var(--line); border-radius:99px; padding:0 7px; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.loc {{ display:flex; gap:6px; align-items:flex-start; margin-top:3px; }}
.loc code {{ font:12px/1.4 ui-monospace,Consolas,monospace; color:var(--muted); background:var(--bg); border:1px solid var(--line); border-radius:5px; padding:2px 6px; overflow-wrap:anywhere; user-select:all; cursor:text; }}
.cp {{ flex:none; font-size:11px; border:1px solid var(--line); background:var(--panel); color:var(--muted); border-radius:5px; padding:2px 7px; cursor:pointer; }}
.cp:hover {{ color:var(--accent); border-color:var(--accent); }}
.vlc {{ flex:none; font-size:11px; font-weight:600; text-decoration:none; border:0; cursor:pointer; font-family:inherit; background:#f08c00; color:#fff !important; border-radius:5px; padding:3px 8px; white-space:nowrap; }}
.vlc:hover {{ background:#d97b00; }}
@media print {{ .cp, .vlc {{ display:none; }} }}
@media (max-width:700px) {{ .grid2 {{ grid-template-columns:1fr; }} .k {{ flex-basis:66px; }} }}
@media print {{ nav.toc, .tools {{ display:none; }} .move {{ break-inside:avoid; }} details.pos > summary .names {{ display:none; }} }}
</style></head><body>
<script src="nav.js"></script>
<div class="wrap">
<h1>My Game Study Guide</h1>
<p class="lede">Every position and move in your game, with the instructionals in your library that teach it. Use <b>Open in VLC</b> to play a video straight from your drive (open this page with <b>Start BJJ Library</b> for the button to work). <a href="index.html">Back to the full library</a> · <a href="report.html">Build a report for chosen positions</a></p>
<div class="stats">
 <div class="stat"><b>{positions}</b><span>positions</span></div>
 <div class="stat"><b>{moves}</b><span>moves</span></div>
 <div class="stat"><b>{strong}</b><span>with a specific chapter or timestamp</span></div>
 <div class="stat"><b>{gaps_n}</b><span>with only course-level picks</span></div>
</div>
<div class="grid2">
 <div class="box"><h2>Most useful instructionals for your game</h2><ol>{top_courses}</ol></div>
 <div class="box"><h2>Weak spots in your library</h2><p class="muted" style="margin:0 0 6px">No chapter in your library is named for these. The picks are courses that probably cover them.</p><ul>{gap_list}</ul></div>
</div>
<div class="legend">
 <span><span class="k k-ch" style="display:inline-block;width:70px">Chapter</span> the chapter title names the move</span>
 <span><span class="k k-ts" style="display:inline-block;width:70px">Timestamp</span> from the course's contents file</span>
 <span><span class="k k-vol" style="display:inline-block;width:70px">Volume</span> the publisher's chapter list names it in this volume</span>
 <span><span class="k k-likely" style="display:inline-block;width:70px">Likely</span> the title strongly suggests it</span>
 <span><span class="k k-course" style="display:inline-block;width:70px">Course</span> chapters not labelled; starts at video 1</span>
</div>
<nav class="toc"><div><span class="lbl">Top</span>{toc_top}</div><div><span class="lbl">Bottom</span>{toc_bot}</div>
<div class="tools"><button data-all="open">Expand all</button><button data-all="close">Collapse all</button><button data-all="moves">Collapse moves</button></div></nav>
{sections}
</div>
<script>
// Collapsible sections: remember which positions are open between visits.
const KEY = 'bjjguide.open';
const load = () => {{ try {{ return JSON.parse(localStorage.getItem(KEY) || '[]'); }} catch (e) {{ return []; }} }};
const save = () => {{ try {{ localStorage.setItem(KEY, JSON.stringify([...document.querySelectorAll('details.pos[open]')].map(d => d.id))); }} catch (e) {{}} }};
load().forEach(id => {{ const d = document.getElementById(id); if (d) d.open = true; }});
document.querySelectorAll('details.pos').forEach(d => d.addEventListener('toggle', save));
function goTo(id) {{
  const d = document.getElementById(id); if (!d) return;
  d.open = true; save();
  d.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  history.replaceState(null, '', '#' + id);
}}
if (location.hash) goTo(location.hash.slice(1));
document.addEventListener('click', ev => {{
  const jump = ev.target.closest('a[href^="#"]');
  if (jump) {{ ev.preventDefault(); goTo(jump.getAttribute('href').slice(1)); return; }}
  const all = ev.target.closest('[data-all]');
  if (all) {{
    const m = all.dataset.all;
    if (m === 'moves') document.querySelectorAll('details.move').forEach(d => d.open = false);
    else document.querySelectorAll('details.pos').forEach(d => {{ d.open = m === 'open'; if (m === 'open') d.querySelectorAll('details.move').forEach(x => x.open = true); }});
    save(); return;
  }}
  const b = ev.target.closest('.cp'); if (!b) return;
  const done = () => {{ b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200); }};
  const fallback = () => {{ const r = document.createRange(); r.selectNodeContents(b.previousElementSibling);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r); try {{ document.execCommand('copy'); done(); }} catch (e) {{}} }};
  if (navigator.clipboard) navigator.clipboard.writeText(b.dataset.p).then(done, fallback); else fallback();
}});
</script>
<script src="open-vlc.js"></script>
</body></html>
"""

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
