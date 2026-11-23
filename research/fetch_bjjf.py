"""Fetch BJJ Fanatics product descriptions for each instructional (research step for the wiki).

Saves raw search results to research/bjjf/<n>.json. Polite: one request every 5 seconds,
backs off on rate limits, and skips courses already fetched (safe to re-run).
"""
import json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'bjjf')
os.makedirs(OUT, exist_ok=True)
SKIP_PAT = re.compile(r'THE ENTIRE APP|Power Building|Giant \(2025\)|One\.Championship|10th Planet Books|Barry Robinson', re.I)


def load_courses():
    src = open(os.path.join(LIB, 'data.js'), encoding='utf-8').read()
    return json.loads(src[src.index('=') + 1:].strip().rstrip(';'))['courses']


def query_for(c):
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', c['t'])
    t = re.sub(r'^(10th Planet Freaks|Go Further Faster|New Wave|Enter The System|Master the Move|Pillars of Defense|'
               r'Systematically Attacking From|Jiu Jitsu for Old Guys|Ageless Jiu Jitsu|Standing2Ground|Daisy Fresh)\s*:?', lambda m: m.group(0), t)
    inst = re.sub(r'\(.*?\)', '', c['i'] or '')
    q = f'{t} {inst}'.replace(':', ' ').replace('&', ' ')
    return re.sub(r'\s+', ' ', q).strip()


def fetch(q):
    url = ('https://bjjfanatics.com/search/suggest.json?q=' + urllib.parse.quote(q) +
           '&resources%5Btype%5D=product&resources%5Blimit%5D=4')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (personal library catalogue)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    courses = load_courses()
    todo = [(i, c) for i, c in enumerate(courses) if not c['dupOf'] and not SKIP_PAT.search(c['path'])]
    print(f'{len(todo)} courses to look up', flush=True)
    for n, (i, c) in enumerate(todo):
        path = os.path.join(OUT, f'{i}.json')
        if os.path.exists(path):
            continue
        q = query_for(c)
        for attempt in range(5):
            try:
                res = fetch(q)
                break
            except Exception as e:  # 429 / network: back off
                wait = 30 * (attempt + 1)
                print(f'  {i}: {e} - waiting {wait}s', flush=True)
                time.sleep(wait)
        else:
            print(f'  {i}: giving up', flush=True)
            continue
        prods = res.get('resources', {}).get('results', {}).get('products', [])
        json.dump({'course': c['path'], 'title': c['t'], 'query': q,
                   'products': [{'title': p['title'], 'handle': p['handle'], 'body': p.get('body', '')} for p in prods]},
                  open(path, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'{n + 1}/{len(todo)} {c["t"][:50]} -> {prods[0]["title"][:60] if prods else "NO RESULT"}', flush=True)
        time.sleep(5)
    print('done', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
