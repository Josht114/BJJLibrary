"""Print courses (index range) with their video names + durations, for writing entries."""
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
src = open('data.js', encoding='utf-8').read(); C = json.loads(src[src.index('=')+1:].strip().rstrip(';'))['courses']
a, b = int(sys.argv[1]), int(sys.argv[2])
full = len(sys.argv) > 3
for i in range(a, b + 1):
    c = C[i]
    if c['dupOf'] or not c['videos']: continue
    names = [v['f'][len(c['path'])+1:] if v['f'] != c['path'] else v['f'] for v in c['videos']]
    tot = sum(v['d'] or 0 for v in c['videos']) // 60
    print(f"## {i} | {c['path']} | {c['t']} | {c['i']} | {len(names)} vids {tot}m")
    shown = names if full or len(names) <= 40 else names[:40] + [f'... +{len(names)-40} more']
    print('   ' + ' ; '.join(re.sub(r'\.(mp4|mkv|flv|avi|m4v|mov)(\.mp4|\.mov)?$', '', n)[:90] + (f" [{(v['d'] or 0)//60}m]" if v.get('d') else '') for n, v in zip(shown, c['videos'])))
