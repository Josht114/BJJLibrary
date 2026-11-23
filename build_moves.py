"""Break the library down by position -> move -> videos. Writes moves.js for the library page.

Matches each video's name, its notes and its chapter list (from the wiki research) against the
moves in moves.py. Run after build_wiki.py:  python build_moves.py
"""
import json, os, re, sys
from moves import MOVES, POSITION_CONTEXT

HERE = os.path.dirname(os.path.abspath(__file__))
# Submission families: the technique word itself must appear (e.g. "armbar" for the armbar moves),
# because their move patterns are positional words like "guard" or "mount".
STRICT = {'chokes', 'guillotine', 'triangle', 'armlocks', 'kimura'}
# Positions that label sections of a course ("5 - Closed Guard"). If a chapter's own section names one of
# these, it isn't filed under a different position just because that position is the course's main topic.
POSITIONAL = ['standing', 'closed-guard', 'half-guard', 'butterfly', 'open-guard', 'mount', 'side-control', 'back', 'turtle-fhl']
MAX_TEXTS = 3


def load(name, var):
    src = open(os.path.join(HERE, name), encoding='utf-8').read()
    return json.loads(src[src.index('=') + 1:].strip().rstrip(';'))


def main():
    wiki = load('wiki.js', 'WIKI')
    entries = [e for e in wiki['entries'] if 'dupOf' not in e]
    comp = {p: [(mid, name, re.compile(rx, re.I)) for mid, name, rx in mv] for p, mv in MOVES.items()}
    ctx = {p: re.compile(rx, re.I) for p, rx in POSITION_CONTEXT.items()}
    hits = {mid: {} for mv in MOVES.values() for mid, _, _ in mv}

    def consider(e, j, text, kind, context, pos_primary, section=''):
        for p, moves in comp.items():
            cx = ctx[p]
            pos_ok = bool(cx.search(text) or cx.search(context))
            if not pos_ok:
                if p in STRICT or pos_primary != p:
                    continue
                if section and any(ctx[q].search(section) for q in POSITIONAL if q != p):
                    continue
            for mid, _, rx in moves:
                if not rx.search(text):
                    continue
                key = (e['path'], j)
                h = hits[mid].setdefault(key, {'kind': kind, 'texts': []})
                if kind == 'video':
                    h['kind'] = 'video'
                if text not in h['texts'] and len(h['texts']) < MAX_TEXTS:
                    h['texts'].append(text)

    for e in entries:
        if 'other' in e['p'] or e['p'][:1] == ['sc-mindset']:
            continue
        primary = e['p'][0]
        for j, f in enumerate(e['files']):
            label = '' if f['numbered'] else f['label']
            vol_title = f['covers'][0] if f['covers'] else ''
            context = ' '.join(x for x in (label, f['folder'], vol_title, e['t']) if x)
            section = ' '.join(x for x in (f['folder'], vol_title) if x)
            if label:
                consider(e, j, label, 'video', ' '.join(x for x in (f['folder'], e['t']) if x), primary, f['folder'])
            if f['note']:
                consider(e, j, f['note'], 'video', context, primary, section)
            for c in f['covers']:
                consider(e, j, c, 'chapter', context, primary, section)
        for sec in e['contents']:  # chapter lists that couldn't be matched to individual files
            for it in sec['items']:
                consider(e, -1, it, 'course', sec['title'] + ' ' + e['t'], primary)

    tree, out = [], {}
    for p, moves in MOVES.items():
        row = []
        for mid, name, _ in moves:
            lst = [[path, j, h['kind'], h['texts']] for (path, j), h in hits[mid].items()]
            # whole videos about the move first, then chapters inside a volume, then course-level contents
            order = {'video': 0, 'chapter': 1, 'course': 2}
            lst.sort(key=lambda x: (order[x[2]], x[0], x[1]))
            out[mid] = lst
            row.append({'id': mid, 'name': name, 'n': len(lst),
                        'courses': len({x[0] for x in lst})})
        tree.append({'pos': p, 'moves': row})
    with open(os.path.join(HERE, 'moves.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.MOVES = ' + json.dumps({'tree': tree, 'hits': out}, ensure_ascii=False) + ';\n')
    total = sum(len(v) for v in out.values())
    empty = [m['name'] for t in tree for m in t['moves'] if not m['n']]
    print(f'moves.js: {sum(len(t["moves"]) for t in tree)} moves, {total} video/chapter matches')
    if empty:
        print('  moves with no matches:', ', '.join(empty))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
