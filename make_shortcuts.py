"""Create Windows shortcuts (.lnk) to every video in _BJJ Library/Shortcuts/<Position>/<Move>/<Gi | No-Gi | Gi & No-Gi>/.

Name:  DESCRIPTION - INSTRUCTOR.lnk. In a move folder the description is the video's chapter(s) about
       that move (from moves.js); otherwise the wiki's per-file note, volume chapter list or a tidied
       file name (wiki.js, research/file_notes.json). Videos with no move go in <Position>/General (no specific move)/.
A video gets a copy in the folder of every move it covers. If two names in a folder clash, a
"(Course Vol 3)" tag is added. The tooltip names the instructional and file.
Skips duplicate copies and non-BJJ folders. The Shortcuts folder is rebuilt from scratch each run.
Run after build_wiki.py:  python make_shortcuts.py
"""
import json, os, re, shutil, subprocess, sys, tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'Shortcuts')
SKIP_PATHS = ('THE ENTIRE APP',)
MAX_NAME = 180          # names are also cut to keep each full path under Windows' 260-character limit
MAX_TITLE = 55          # very long instructional titles are shortened to leave room for the moves
GENERAL = 'General (no specific move)'
# Each move folder is split by the course's style (catalog.json "g"); courses that teach both, or are unlabelled,
# go in "Gi & No-Gi".
KIT = {'gi': 'Gi', 'nogi': 'No-Gi', 'both': 'Gi & No-Gi'}


def load(name):
    src = open(os.path.join(HERE, name), encoding='utf-8').read()
    return json.loads(src[src.index('=') + 1:].strip().rstrip(';'))


def clean(s):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', s)          # characters Windows doesn't allow in names
    s = s.replace('：', ' ').replace('’', "'")
    return re.sub(r'\s+', ' ', s).strip(' .')


def full_title(c):
    """Course title without the instructor's name, e.g. "New Wave: Closed Guard"."""
    t = c['t'].replace('：', ':')
    for inst in re.split(r'\s*(?:&|,| and )\s*', re.sub(r'\s*\(.*?\)', '', c['i'] or '')):
        if inst.strip():
            t = re.sub(re.escape(inst.strip()) + r"(?:'s)?", '', t, flags=re.I)
    t = re.sub(r'\(\s*(gi|no-? ?gi)\s*\)', lambda m: m.group(1), t, flags=re.I)     # "(Gi)" -> "Gi"
    t = re.sub(r'(?i)^\s*by\b|\bby\s*$', '', re.sub(r'\s+', ' ', t)).strip(' -–,.')
    return t or 'Course'


def short_title(c):
    """Short course name: the part before a colon/dash ("New Wave: Closed Guard" -> "New Wave"),
    plus Gi / No-Gi when the title says so, cut to about 30 characters."""
    t = full_title(c)
    head = re.split(r'\s+[-–]\s+|:\s*', t, maxsplit=1)[0].strip()
    if len(head) >= 4:
        t = head
    t = clean(t)
    if len(t) > 30:
        t = t[:30].rsplit(' ', 1)[0].rstrip(' ,&-')
    kit = re.search(r'(?i)\b(no-? ?gi|gi)\s*\)?\s*$', c['t'])
    if kit and not re.search(r'(?i)\b' + re.escape(kit.group(1)) + r'\s*$', t):
        t += ' ' + ('No-Gi' if 'no' in kit.group(1).lower() else 'Gi')
    return t


VOL_RX = re.compile(r'(?i)\b(?:vol(?:ume)?|part|pt|disc|dvd|ep(?:isode)?)[ ._-]*(\d+)')


def vol_label(c, j, v):
    """" Vol 3" from the volume/part number in the file name (the last one, so "System Part 1 Vol. 4" -> 4),
    " Vol 1 Part 2" when the course has volume subfolders, else the file's place in the course."""
    if len(c['videos']) == 1:
        return ''
    parts = v['f'].split('/')[len(c['path'].split('/')):]
    base = parts[-1]
    nums = VOL_RX.findall(re.sub(re.escape(c['t']), '', base, flags=re.I)) or VOL_RX.findall(base)
    sub = [VOL_RX.findall(p) or re.findall(r'^(\d+)\b', p) for p in parts[:-1]]
    sub = [s[-1] for s in sub if s]
    if nums and re.search(r'(?i)\bbonus\b', base):
        return f' Bonus {int(nums[-1])}'
    if nums and sub:
        return f' Vol {int(sub[-1])} Part {int(nums[-1])}'
    if nums:
        return f' Vol {int(nums[-1])}'
    return f' Part {j + 1}'


def subtitle(c):
    """The part of the title after the colon/dash ("New Wave: Side Attacks" -> "Side Attacks"), + Gi/No-Gi."""
    t = full_title(c)
    bits = re.split(r'\s+[-–]\s+|:\s*', t, maxsplit=1)
    return clean(bits[1] if len(bits) > 1 and len(bits[1]) >= 4 else t)


def fit(title, vol, room):
    """title + vol in at most `room` characters, shortening the title at a word."""
    if len(title) + len(vol) <= room:
        return title + vol
    keep = max(6, room - len(vol) - 1)
    return title[:keep].rsplit(' ', 1)[0].rstrip(' ,&-:') + '…' + vol


STOP = set('by the of and a an in on to from with for gi nogi no bjj jiu jitsu jj fanatics vol volume part pt disc dvd '
           'chapter ch ep episode mp4 mkv m4v p hd web dl x264 h264 720p 1080p full series instructional'.split())
GENERIC = re.compile(r'(?i)^(intro(duction)?|overview|conclusion|summary|outro|final thoughts|closing( thoughts)?|'
                     r'welcome|preview|trailer|bonus|recap|review)\b.{0,25}$')
MAX_DESC = 95


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def tidy(text, c):
    """A readable description from a file name / chapter / note: drops the extension, the course title,
    the instructor and volume numbering. Returns '' when nothing descriptive is left."""
    t = re.sub(r'(?i)\.(mp4|mkv|m4v|avi|flv|mov|webm|wmv)(\.mp4)?$', '', text)
    pre = c.get('_prefix')
    if pre and t.lower().startswith(pre.lower()):         # text every file name in the course starts with
        t = t[len(pre):]
    t = t.replace('_', ' ').replace('⧸', '/').replace('：', ':')
    t = re.sub(r'(?i)\b(720p?|1080p?|480p|web-?dl|x264|h264)\b', ' ', t)
    # the course title / instructor written into the file name ("... Closed Guard by John Danaher Vol 8")
    for phrase in [c['t'], re.sub(r'\s*\(.*?\)', '', c['t']), re.sub(r'\s*\(.*?\)', '', c['i'] or '')] + \
                  re.split(r'\s*(?:&|,| and )\s*', re.sub(r'\s*\(.*?\)', '', c['i'] or '')):
        w = words(phrase)
        if len(w) >= 2 or (w and len(w[0]) > 3):
            t = re.sub(r'(?i)' + r"[^a-z0-9']+".join(map(re.escape, w)) + r"(?:'s)?", ' ', t)
    t = re.sub(r'(?i)\bby\s*$|^\s*by\b', ' ', t.strip(' -–.:,'))
    lead = r'(?i)^[\s\-–.:,#()\[\]]*(?:(?:vol(?:ume)?|part|pt|disc|dvd|chapter|ch|ep(?:isode)?)\.?\s*\d+[a-z]?|\d+(?:[.\-]\d+)*)[\s\-–.:)\]]*'
    for _ in range(3):
        t = re.sub(lead, '', t)
    t = re.sub(r'(?i)[\s\-–(]*(?:vol(?:ume)?|part|pt)\.?\s*\d+\)?\s*$', '', t)       # trailing "Part 2"
    t = re.sub(r'(?<=[A-Za-z])\s+\d{1,3}\s+[-–]\s+', ' - ', t)                      # "Section 03 - Chapter"
    t = re.sub(r'\s+', ' ', t).strip(' -–.:,()')
    meaningful = [w for w in words(t) if w not in STOP and not w.isdigit()
                  and w not in words(c['t'] + ' ' + (c['i'] or ''))]
    if not meaningful and len(words(t)) < 3:
        return ''
    if t.isupper() and len(t) > 6:
        t = t.title()
    return clean(t)


def shorten(s, n=MAX_DESC):
    s = re.split(r'(?<=[a-z0-9)])\. ', s, maxsplit=1)[0].rstrip('.')       # first sentence of a note
    if len(s) <= n:
        return s
    return s[:n].rsplit(' ', 1)[0].rstrip(' ,&-:;(') + '…'


def join_items(items, n=MAX_DESC):
    """Join chapter titles until the description is long enough, skipping 'Introduction' and the like."""
    out = []
    for it in items:
        if GENERIC.match(it) or it in out:
            continue
        if out and len('; '.join(out + [it])) > n:
            break
        out.append(it)
        if len('; '.join(out)) > 45:
            break
    return '; '.join(out)


def describe(c, f, texts=None):
    """What's in video f (a wiki file row). texts: the chapter titles that matched the folder's move."""
    if texts:
        got = [tidy(x, c) for x in texts]
        got = [g for g in got if g and not GENERIC.match(g)]
        spaced = [g for g in got if ' ' in g]                 # drop "ElectricPendulumToDogfight" style file names
        got = spaced or got
        if got:
            return shorten(join_items(got) or got[0])
    if f['note']:
        return shorten(clean(f['note']))
    if f['covers']:
        items = [clean(x) for x in f['covers']]
        if len(items[0]) >= 25 or len(items) == 1:
            return shorten(items[0])
        return shorten(join_items(items) or items[0])
    t = tidy(f['label'], c) or tidy(f['file'], c)
    if t:
        return shorten(t)
    return ''


def balance(s):
    """Drop an unmatched '(' left over from shortening ("Vs Knee Turned In (Back To Bolo")."""
    if s.count('(') > s.count(')'):
        s = s[:s.rfind('(')].rstrip(' -;,') + ' ' + s[s.rfind('(') + 1:]
    return re.sub(r'\s+', ' ', s.replace(')', '') if s.count(')') > s.count('(') else s).strip()


def main():
    lib, mv = load('data.js'), load('moves.js')
    wiki = {e['path']: e for e in load('wiki.js')['entries'] if 'dupOf' not in e}
    hit_texts = {}
    for mid, hits in mv['hits'].items():
        for path, j, kind, texts in hits:
            hit_texts[(mid, path, j)] = texts
    pos_name = dict(lib['positions'])
    move_name, move_pos = {}, {}
    for t in mv['tree']:
        for m in t['moves']:
            move_name[m['id']], move_pos[m['id']] = m['name'], t['pos']
    video_moves = defaultdict(list)                    # (course path, video index) -> [move ids]
    for mid, hits in mv['hits'].items():
        for path, j, kind, texts in hits:
            if j >= 0 and mid not in video_moves[(path, j)]:
                video_moves[(path, j)].append(mid)

    plan = []
    for c in lib['courses']:
        if c['dupOf'] or 'other' in c['p'] or c['path'].startswith(SKIP_PATHS) or not c['videos']:
            continue
        inst = clean(re.sub(r'\s*\(.*?\)', '', c['i'] or '') or 'Unknown')   # drop notes like "(Art of Jiu Jitsu)"
        title = clean(c['t'])
        if len(title) > MAX_TITLE:                                               # cut very long titles at a word
            title = title[:MAX_TITLE].rsplit(' ', 1)[0].rstrip(' ,&-') + '…'
        for j, v in enumerate(c['videos']):
            mids = video_moves.get((c['path'], j), [])
            # keep the moves in the order they appear in moves.py
            order = {m: i for i, m in enumerate(move_name)}
            mids = sorted(mids, key=order.get)
            # One copy per move folder (Position\Move), named after that folder's move and position only.
            # Videos with no move go in <course's main position>\General, named POSITION-INSTRUCTIONAL-INSTRUCTOR.
            spots = {}
            for m in mids:
                key = (clean(pos_name.get(move_pos[m], move_pos[m])), clean(move_name[m]))
                spots.setdefault(key, []).extend(hit_texts.get((m, c['path'], j), []))
            if not spots:
                spots = {(clean(pos_name.get(c['p'][0], c['p'][0])), None): []}
            if j == 0 and len(c['videos']) > 2:              # shared file-name prefix, e.g. "Mastering The Omoplata 03 - "
                pre = os.path.commonprefix([x['f'].split('/')[-1].lower() for x in c['videos']])
                pre = re.match(r"^(.*?[a-z].*?)[^a-z']*(?:\b[a-z']*)?$", pre)
                pre = re.sub(r'[\s\-–_.:]*(?:\d+)?$', '', pre.group(1)) if pre else ''
                c['_prefix'] = pre if len(pre) >= 8 else ''
            wf = wiki[c['path']]['files'][j] if c['path'] in wiki else None
            for (pos_label, move), texts in spots.items():
                folder = os.path.join(pos_label, move or GENERAL, KIT.get(c['g'], KIT['both']))
                # room for the name: full path must stay under 260 chars (incl. ".lnk")
                budget = min(MAX_NAME, 259 - len(os.path.join(OUT, folder)) - 1 - len('.lnk'))
                desc = (describe(c, wf, texts) if wf else '') or fit(short_title(c), vol_label(c, j, v), 60)
                if len(desc) < 16 or GENERIC.match(desc):              # "Intro", "Concepts": say which course
                    desc = f'{short_title(c)} - {desc}' if not desc.startswith(short_title(c)) else desc
                tail = f' - {inst}'
                room = budget - len(tail) - 30                            # leave room for a " (Course Vol 3)" tag
                if len(desc) > room:
                    desc = desc[:room].rsplit(' ', 1)[0].rstrip(' ,&-:;(') + '…'
                name = f'{balance(desc)}{tail}'
                plan.append({'folder': folder, 'name': name, 'budget': budget,
                             'short': short_title(c), 'full': subtitle(c), 'vol': vol_label(c, j, v),
                             'target': os.path.join(ROOT, *v['f'].split('/')), 'desc': f"{c['t']} ({c['i']}) - {v['f'].split('/')[-1]}"[:250]})

    # make names unique within each folder: clashing names get a short course + volume tag,
    # e.g. "Omoplata-Closed Guard-John Danaher (New Wave Vol 3)"
    # If the short course name still clashes (two courses with the same start), use the full course title.
    seen = Counter((p['folder'], p['name'].lower()) for p in plan)
    clashing = [p for p in plan if seen[(p['folder'], p['name'].lower())] > 1]
    for p in clashing:
        p['room'] = p['budget'] - len(p['name']) - 3 - 5         # leave room for " (…)" and a " [12]" fallback
        p['try'] = f"{p['name']} ({fit(p['short'], p['vol'], p['room'])})"
    seen1 = Counter((p['folder'], p['try'].lower()) for p in clashing)
    for p in clashing:
        if seen1[(p['folder'], p['try'].lower())] > 1 and p['full'] != p['short']:
            p['try'] = f"{p['name']} ({fit(p['full'], p['vol'], p['room'])})"
        p['name'] = p['try']
    seen2 = Counter((p['folder'], p['name'].lower()) for p in plan)
    count = Counter()
    for p in plan:
        k = (p['folder'], p['name'].lower())
        if seen2[k] > 1:                       # same course and volume twice (rare): number them
            count[k] += 1
            p['name'] = f"{p['name']} [{count[k]}]"
    for p in plan:
        p['lnk'] = os.path.join(OUT, p['folder'], p['name'] + '.lnk')

    if '--dry-run' in sys.argv:
        import random
        random.seed(int(sys.argv[-1]) if sys.argv[-1].isdigit() else 1)
        for p in random.sample(plan, 40):
            print(p['folder'], '|', p['name'])
        print(len(plan), 'shortcuts planned in', len({p['folder'] for p in plan}), 'folders')
        return

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for f in {p['folder'] for p in plan}:
        os.makedirs(os.path.join(OUT, f), exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), 'bjj_shortcuts.json')
    json.dump([{'lnk': p['lnk'], 'target': p['target'], 'desc': p['desc']} for p in plan],
              open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    # Uses the native IShellLinkW interface: WScript.Shell can't handle Unicode file names
    # (e.g. the full-width colon or "⧸" some instructionals use).
    ps = r'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
[ComImport, Guid("00021401-0000-0000-C000-000000000046")] class CShellLink {}
[ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
interface IShellLinkW {
  void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder f, int c, IntPtr fd, int fl);
  void GetIDList(out IntPtr p); void SetIDList(IntPtr p);
  void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int c);
  void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int c);
  void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int c);
  void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetHotkey(out short h); void SetHotkey(short h);
  void GetShowCmd(out int c); void SetShowCmd(int c);
  void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int c, out int i);
  void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string s, int i);
  void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string s, int r);
  void Resolve(IntPtr h, int f);
  void SetPath([MarshalAs(UnmanagedType.LPWStr)] string s);
}
public static class Lnk {
  public static void Make(string lnk, string target, string args, string workdir, string desc) {
    var l = (IShellLinkW)new CShellLink();
    l.SetPath(target);
    if (args != null) l.SetArguments(args);
    l.SetWorkingDirectory(workdir);
    l.SetDescription(desc);
    ((IPersistFile)l).Save(lnk, true);
  }
}
"@
$items = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8 | ConvertFrom-Json
$fso = New-Object -ComObject Scripting.FileSystemObject
$ok = 0; $bad = 0; $short = 0
foreach ($it in $items) {
  try {
    $t = $it.target
    if ($t.Length -ge 259) {
      # Paths of 260+ characters break shortcuts (Windows stores the long path, which many players can't open).
      # Open those through Explorer with the file's short 8.3 path instead; it opens in the default player.
      $sp = $fso.GetFile($t).ShortPath
      [Lnk]::Make($it.lnk, "$env:SystemRoot\explorer.exe", ('"' + $sp + '"'), [IO.Path]::GetDirectoryName($sp), $it.desc); $short++
    } else {
      [Lnk]::Make($it.lnk, $t, $null, [IO.Path]::GetDirectoryName($t), $it.desc)
    }
    $ok++ }
  catch { $bad++; Write-Output ("FAILED: " + $it.lnk + " : " + $_.Exception.Message) }
}
Write-Output "created $ok shortcuts ($short using short paths), $bad failed"
'''
    script = os.path.join(tempfile.gettempdir(), 'bjj_shortcuts.ps1')
    open(script, 'w', encoding='utf-8-sig').write(ps)
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, tmp],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(r.stdout.strip()[-3000:], r.stderr.strip()[-2000:])
    print(f'{len(plan)} shortcuts in {len({p["folder"] for p in plan})} position/move/gi folders under {OUT}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
