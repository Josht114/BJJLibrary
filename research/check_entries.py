"""Check research entries: course paths exist, file notes match real video names, handles exist in fetched data."""
import glob, json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
src = open('data.js', encoding='utf-8').read(); C = {c['path']: c for c in json.loads(src[src.index('=')+1:].strip().rstrip(';'))['courses']}
raw = {}
for f in glob.glob('research/bjjf/*.json'):
    r = json.load(open(f, encoding='utf-8')); raw[r['course']] = {p['handle'] for p in r['products']}
bad = 0; n = 0
for f in sorted(glob.glob('research/entries/*.json')):
    for path, e in json.load(open(f, encoding='utf-8')).items():
        n += 1
        c = C.get(path)
        if not c: print('NO COURSE:', path); bad += 1; continue
        names = {v['f'].split('/')[-1] for v in c['videos']}
        for k in e.get('files', {}):
            if k not in names: print('NO FILE:', path, '->', k); bad += 1
        h = e.get("bjjf")
        for hh in (e.get("bjjf_folders") or {}).values():
            if hh not in raw.get(path, set()): print("HANDLE NOT FETCHED:", path, hh); bad += 1
        if h and h not in raw.get(path, set()): print('HANDLE NOT FETCHED:', path, h); bad += 1
print(f'{n} entries checked, {bad} problems')
