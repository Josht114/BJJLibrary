"""Build the wiki: an "_ABOUT THIS INSTRUCTIONAL.txt" in every course folder + wiki.js for wiki.html.

Inputs
  data.js                     library scan (python build.py)
  research/entries/*.json     hand-written research: {course path: entry}
  research/bjjf/<n>.json      fetched BJJ Fanatics descriptions (research/fetch_bjjf.py)

Entry fields (all optional except overview):
  overview   paragraph(s) in plain English
  for        who it suits
  key        list of key topics / takeaways
  bjjf       BJJ Fanatics product handle whose volume list matches this course (or null)
  files      {video file name: "what this file covers"} overrides
  contents   [{"title": ..., "items": [...]}] hand-written contents when no product listing exists
  sources    list of extra source notes/URLs
Run:  python build_wiki.py          (add --no-txt to skip writing the text files)
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'research'))
from bjjf_parse import parse  # noqa: E402

TXT_NAME = '_ABOUT THIS INSTRUCTIONAL.txt'
POS_NAMES = {}


def load_lib():
    src = open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()
    lib = json.loads(src[src.index('=') + 1:].strip().rstrip(';'))
    POS_NAMES.update(dict(lib['positions']))
    return lib


def load_entries():
    entries = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'research', 'entries', '*.json'))):
        entries.update(json.load(open(f, encoding='utf-8')))
    return entries


def load_raw():
    """course path -> list of fetched products"""
    out = {}
    for f in glob.glob(os.path.join(HERE, 'research', 'bjjf', '*.json')):
        r = json.load(open(f, encoding='utf-8'))
        out[r['course']] = r['products']
    return out


def fmt(s):
    if not s:
        return ''
    h, r = divmod(int(s), 3600)
    m, x = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}:{x:02d}'


def clean_chapter(fname):
    """Readable chapter title from a video file name."""
    t = re.sub(r'\.(mp4|mkv|m4v|avi|flv|mov|webm|wmv)(\.mp4|\.mov)?$', '', fname, flags=re.I)
    t = re.sub(r'(?i)\.?(720p?|1080p?|_720|\.ID2K|WEB-DL.*|x264.*|H264.*)$', '', t)
    t = re.sub(r'(?i)^freak bros technique - \w+ - ', '', t)
    t = re.sub(r'\s*\((Craig Jones)\)\s*$', '', t)
    t = t.replace('_', ' ').replace('⧸', '/').replace('：', ':')
    return re.sub(r'\s+', ' ', t).strip(' .-')


def is_numbered(fname):
    """True when the file name says nothing beyond a volume/part number."""
    t = clean_chapter(fname)
    t = re.sub(r'(?i)(vol(ume)?|part|disc|dvd)\s*\d+', '', t)
    t = re.sub(r'\d+', '', t)
    return len(re.sub(r'[^A-Za-z]', '', t)) < 3 or bool(re.search(r'(?i)(vol(ume)?|part)\s*\d+\s*$', clean_chapter(fname)))


def file_breakdown(course, entry, vols):
    """List of {file, label, dur, covers[]} for every video."""
    vids = course['videos']
    overrides = entry.get('files', {}) if entry else {}
    use_vols = vols and len(vols) == len(vids)
    rows = []
    for i, v in enumerate(vids):
        base = v['f'].split('/')[-1]
        sub = '/'.join(v['f'].split('/')[len(course['path'].split('/')):-1]) if '/' in v['f'] else ''
        label = clean_chapter(base)
        covers = []
        if use_vols:
            vol = vols[i]
            if vol['title']:
                covers.append(vol['title'])
            covers += vol['items']
        note = overrides.get(base)
        rows.append({'file': base, 'folder': sub, 'label': label, 'dur': v.get('d'), 'note': note,
                     'covers': covers, 'numbered': is_numbered(base)})
    return rows, use_vols


def build_entry(course, entry, raw):
    vols, source = [], None
    handle = (entry or {}).get('bjjf')
    if handle:
        prod = next((p for p in raw.get(course['path'], []) if p['handle'] == handle), None)
        if prod:
            _, vols = parse(prod['body'])
            source = f'https://bjjfanatics.com/products/{handle}'
    files, mapped = file_breakdown(course, entry, vols)
    # Courses split into subfolders that are separate products: {"subfolder": handle}
    for sub, h in ((entry or {}).get('bjjf_folders') or {}).items():
        prod = next((p for p in raw.get(course['path'], []) if p['handle'] == h), None)
        if not prod:
            continue
        _, svols = parse(prod['body'])
        rows = [f for f in files if f['folder'] == sub]
        if svols and len(svols) == len(rows):
            for f, v in zip(rows, svols):
                f['covers'] = ([v['title']] if v['title'] else []) + v['items']
            mapped = True
            src = f'https://bjjfanatics.com/products/{h}'
            source = source or src
            if src not in (entry.get('sources') or []):
                entry.setdefault('sources', []).append(src)
    contents = (entry or {}).get('contents') or ([{'title': f"Volume {v['n']}" + (f": {v['title']}" if v['title'] else ''),
                                                   'items': v['items']} for v in vols] if vols and not mapped else [])
    total = sum(v.get('d') or 0 for v in course['videos'])
    sources = ([source] if source else []) + (entry or {}).get('sources', [])
    return {
        'path': course['path'], 't': course['t'], 'i': course['i'], 'g': course['g'], 'p': course['p'],
        'summary': course['s'], 'overview': (entry or {}).get('overview') or course['s'],
        'for': (entry or {}).get('for', ''), 'key': (entry or {}).get('key', []),
        'files': files, 'mapped': mapped, 'contents': contents, 'total': total, 'nvideos': len(course['videos']),
        'sources': sources, 'researched': bool(entry and entry.get('overview')),
    }


def wrap(text, width=88, indent=''):
    out, line = [], indent
    for w in text.split():
        if len(line) + len(w) + 1 > width and line.strip():
            out.append(line.rstrip())
            line = indent
        line += w + ' '
    if line.strip():
        out.append(line.rstrip())
    return '\n'.join(out)


def to_text(e, dup_paths):
    gi = {'gi': 'Gi', 'nogi': 'No-Gi', 'both': 'Gi & No-Gi'}.get(e['g'], '')
    bar = '=' * 88
    L = [bar, e['t'].upper(), bar]
    meta = [x for x in [e['i'] and f'Instructor: {e["i"]}', gi and f'Style: {gi}',
                        f'Videos: {e["nvideos"]}', e['total'] and f'Total running time: {fmt(e["total"])}'] if x]
    L.append(' | '.join(meta))
    L.append('Positions: ' + ', '.join(POS_NAMES.get(p, p) for p in e['p']))
    L += ['', 'OVERVIEW', '-' * 8, wrap(e['overview'])]
    if e['for']:
        L += ['', "WHO IT'S FOR", '-' * 12, wrap(e['for'])]
    if e['key']:
        L += ['', 'KEY TOPICS', '-' * 10] + [wrap(k, indent='  * ').replace('  * ', '  * ', 1) for k in e['key']]
    L += ['', "WHAT'S IN EACH FILE", '-' * 19]
    folder = None
    for n, f in enumerate(e['files'], 1):
        if f['folder'] != folder and f['folder']:
            L += ['', f'[{f["folder"]}]']
        folder = f['folder']
        dur = f' ({fmt(f["dur"])})' if f['dur'] else ''
        L.append(f'{n:>3}. {f["file"]}{dur}')
        if f['note']:
            L.append(wrap(f['note'], indent='       '))
        if f['covers']:
            for c in f['covers']:
                L.append(wrap(c, indent='       - ').replace('       - ', '       - ', 1))
        elif not f['note'] and not f['numbered'] and f['label'] != f['file']:
            L.append(f'       {f["label"]}')
    if e['contents']:
        L += ['', 'COURSE CONTENTS (as listed by the publisher; the files are not split the same way)', '-' * 40]
        for sec in e['contents']:
            L.append(f'  {sec["title"]}')
            L += [f'     - {it}' for it in sec['items']]
    if not e['mapped'] and not e['contents'] and all(f['numbered'] and not f['note'] for f in e['files']) and len(e['files']) > 1:
        L += ['', '  (The files are only numbered and no chapter list was found, so per-file detail is not available.)']
    if dup_paths:
        L += ['', 'OTHER COPIES IN YOUR LIBRARY', '-' * 28] + [f'  F:\\instructionals\\VIDEOS\\{p.replace("/", chr(92))}' for p in dup_paths]
    if e['sources']:
        L += ['', 'SOURCES', '-' * 7] + [f'  {s}' for s in e['sources']]
    L += ['', 'Generated by the BJJ Library wiki (_BJJ Library/build_wiki.py). Overviews are written summaries,',
          'not publisher text; chapter lists come from the publisher listing or the file names.', '']
    return '\n'.join(L)


def txt_target(course):
    """Where the text file goes: inside the course folder, or beside a single-file course."""
    full = os.path.join(ROOT, *course['path'].split('/'))
    if os.path.isdir(full):
        return os.path.join(full, TXT_NAME)
    stem = os.path.splitext(os.path.basename(full))[0]
    return os.path.join(os.path.dirname(full), f'_ABOUT {stem}.txt')


def main():
    write_txt = '--no-txt' not in sys.argv
    lib, entries, raw = load_lib(), load_entries(), load_raw()
    courses = lib['courses']
    dups = {}
    for c in courses:
        if c['dupOf']:
            dups.setdefault(c['dupOf'], []).append(c['path'])
    wiki, written, researched = [], 0, 0
    by_path = {c['path']: c for c in courses}
    for c in courses:
        if not c['videos']:
            continue
        if c['dupOf']:
            wiki.append({'path': c['path'], 'dupOf': c['dupOf'], 't': c['t'], 'note': c['note']})
            src = by_path.get(c['dupOf'])
            if write_txt and src:
                e = build_entry(src, entries.get(src['path']), raw)
                e['files'], _ = file_breakdown(c, entries.get(src['path']), [])
                if e['mapped'] or len(c['videos']) == len(src['videos']):
                    e['files'] = [dict(f, covers=o['covers'], note=o['note']) for f, o in
                                  zip(e['files'], build_entry(src, entries.get(src['path']), raw)['files'])]
                open(txt_target(c), 'w', encoding='utf-8').write(
                    to_text(e, [src['path']]).replace('OTHER COPIES IN YOUR LIBRARY', 'MAIN COPY IN YOUR LIBRARY'))
                written += 1
            continue
        e = build_entry(c, entries.get(c['path']), raw)
        researched += e['researched']
        wiki.append(e)
        if write_txt:
            try:
                open(txt_target(c), 'w', encoding='utf-8').write(to_text(e, dups.get(c['path'], [])))
                written += 1
            except OSError as err:
                print('  could not write', txt_target(c), err)
    with open(os.path.join(HERE, 'wiki.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.WIKI = ' + json.dumps({'entries': wiki, 'positions': lib['positions']}, ensure_ascii=False) + ';\n')
    print(f'wiki.js: {len([w for w in wiki if "dupOf" not in w])} instructionals ({researched} with researched write-ups); '
          f'{written} text files written')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
