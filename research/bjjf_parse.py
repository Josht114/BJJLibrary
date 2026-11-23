"""Turn fetched BJJ Fanatics descriptions into structured contents (volumes -> chapter titles)."""
import html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'bjjf')
NUM_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
             'eleven': 11, 'twelve': 12}
VOL_RE = re.compile(r'^\s*(?:vol(?:ume)?|part|disc|dvd|chapter)\.?\s*[#:]?\s*(\d+|' + '|'.join(NUM_WORDS) + r')\b\s*[:\-–—.]?\s*(.*)$', re.I)
STOP_RE = re.compile(r'what does it (all )?cost|\$\d|money.?back|guarantee|instant(ly)? access|add to cart|'
                     r'order now|buy now|check out (a|the) free sample|limited time', re.I)
STOP_WORDS = {'the', 'a', 'an', 'by', 'and', 'of', 'to', 'for', 'with', 'in', 'on', 'from', 'your', 'bjj', 'jiu', 'jitsu',
              'gi', 'nogi', 'no', 'vol', 'volume', 'part'}


def text_lines(body):
    b = re.sub(r'(?is)<(script|style|iframe).*?</\1>', ' ', body)
    b = re.sub(r'(?i)<\s*(br|/p|/li|/h\d|/div|li|p|h\d|div|tr|/tr)\b[^>]*>', '\n', b)
    b = re.sub(r'<[^>]+>', ' ', b)
    b = html.unescape(b).replace('�', ' ').replace('\xa0', ' ')
    lines = []
    for ln in b.split('\n'):
        ln = re.sub(r'\s+', ' ', ln).strip(' -•*·')
        if ln:
            lines.append(ln)
    return lines


def tidy(s):
    s = re.sub(r'^\(?\d{1,2}:\d{2}(?::\d{2})?\)?\s*[-–—:]?\s*', '', s)      # leading timestamp
    s = re.sub(r'\s*[-–—(]?\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)?$', '', s)      # trailing timestamp
    s = s.strip(' -–—:"\'')
    if s.isupper() and len(s) > 3:
        s = s.title().replace("'S ", "'s ").replace('’S ', '’s ')
    return s


def parse(body):
    """-> (intro_lines, [ {n, title, items[]} ])"""
    lines = text_lines(body)
    intro, vols, cur = [], [], None
    for ln in lines:
        if STOP_RE.search(ln) and vols:
            break
        m = VOL_RE.match(ln)
        if m and len(ln) < 120:
            n = m.group(1).lower()
            n = NUM_WORDS.get(n, None) or int(n)
            rest = tidy(m.group(2) or '')
            cur = {'n': n, 'title': rest, 'items': []}
            # a repeated volume number means a new listing (e.g. a summary then the details): merge
            prev = next((v for v in vols if v['n'] == n), None)
            if prev:
                cur = prev
                if rest and not prev['title']:
                    prev['title'] = rest
            else:
                vols.append(cur)
            continue
        if cur is None:
            if len(intro) < 40:
                intro.append(ln)
            continue
        if len(ln) > 160 or re.search(r'https?://', ln):
            continue
        t = tidy(ln)
        if t and t.lower() not in {'so, what exactly do you get?', 'what exactly do you get?'} and t not in cur['items']:
            cur['items'].append(t)
    vols = [v for v in vols if v['items'] or v['title']]
    vols.sort(key=lambda v: v['n'])
    return intro, vols


def tokens(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP_WORDS}


def match_score(course_title, instructor, product_title):
    want = tokens(course_title) | tokens(instructor or '')
    got = tokens(product_title)
    if not want or not got:
        return 0.0
    return len(want & got) / len(want | got) ** 0.5 / len(want) ** 0.5  # cosine-ish overlap


def best_product(rec, instructor):
    best, score = None, 0.0
    for p in rec['products']:
        s = match_score(rec['title'], instructor, p['title'])
        if s > score:
            best, score = p, s
    return best, score


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    rec = json.load(open(os.path.join(RAW, sys.argv[1] + '.json'), encoding='utf-8'))
    p = rec['products'][int(sys.argv[2]) if len(sys.argv) > 2 else 0]
    intro, vols = parse(p['body'])
    print(p['title'])
    for v in vols:
        print(f"Vol {v['n']}: {v['title']}  ({len(v['items'])} items)")
        for it in v['items'][:6]:
            print('   -', it)
