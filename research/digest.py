"""Condensed view of fetched BJJ Fanatics data for writing entries: python research/digest.py <from> <to> [maxitems]"""
import glob, json, os, re, sys
sys.path.insert(0, 'research'); sys.stdout.reconfigure(encoding='utf-8')
from bjjf_parse import parse, best_product, match_score
src = open('data.js', encoding='utf-8').read(); C = json.loads(src[src.index('=')+1:].strip().rstrip(';'))['courses']
done = set()
for f in glob.glob('research/entries/*.json'): done |= set(json.load(open(f, encoding='utf-8')))
a, b = int(sys.argv[1]), int(sys.argv[2]); mx = int(sys.argv[3]) if len(sys.argv) > 3 else 5
for i in range(a, b + 1):
    p = f'research/bjjf/{i}.json'
    if not os.path.exists(p): continue
    rec = json.load(open(p, encoding='utf-8')); c = next(x for x in C if x['path'] == rec['course'])
    print(f"\n## {i} {c['t']} | {c['i']} | {len(c['videos'])} files: " + ', '.join(v['f'].split('/')[-1][:40] for v in c['videos'][:3]))
    for p2 in rec['products']:
        s = match_score(rec['title'], c['i'], p2['title']); intro, vols = parse(p2['body'])
        print(f"   [{s:.2f}] {p2['title']} ({p2['handle']}) vols={len(vols)}")
    best, s = best_product(rec, c['i'])
    if best and s >= 0.3:
        intro, vols = parse(best['body'])
        txt = ' '.join(intro)[:160]
        print('   INTRO:', txt)
        for v in vols:
            print(f"   V{v['n']} {v['title'][:50]}: " + ' | '.join(x[:45] for x in v['items'][:mx]) + (f' (+{len(v["items"])-mx})' if len(v['items']) > mx else ''))
