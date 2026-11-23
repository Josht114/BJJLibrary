"""Rebuild data.js from the video folders + catalog.json.

Run this whenever you add new instructionals:  python build.py
New folders that aren't in catalog.json show up under "Uncategorised" in the app.
"""
import json, os, sys, unicodedata
from scan import ROOT, units, natural_key

HERE = os.path.dirname(os.path.abspath(__file__))
DOC_EXT = {'.pdf', '.xlsx', '.txt', '.rtf'}
IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp'}


def find_extras(rel):
    """Cover image + documents directly inside a course folder."""
    p = os.path.join(ROOT, rel)
    cover, docs = None, []
    if os.path.isdir(p):
        for dp, dn, fn in os.walk(p):
            for f in sorted(fn, key=natural_key):
                ext = os.path.splitext(f)[1].lower()
                r = os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, '/')
                if ext in IMG_EXT and cover is None:
                    cover = r
                elif ext in DOC_EXT and not f.startswith('_ABOUT'):  # skip the wiki's own text files
                    docs.append(r)
    return cover, docs


def ts_duration(fh, size):
    """MPEG-TS length from the first and last video PTS timestamps."""
    def pts_list(data):
        out = []
        start = data.find(b'\x47')
        while start >= 0 and start + 188 <= len(data) and data[start + 188 if start + 188 < len(data) else start] != 0x47:
            start = data.find(b'\x47', start + 1)
        for p in range(max(start, 0), len(data) - 188, 188):
            pkt = data[p:p + 188]
            if pkt[0] != 0x47 or not pkt[1] & 0x40:
                continue
            off = 4
            if pkt[3] & 0x20:
                off += 1 + pkt[4]
            pes = pkt[off:]
            if len(pes) > 14 and pes[:3] == b'\x00\x00\x01' and 0xE0 <= pes[3] <= 0xEF and pes[7] & 0x80:
                b = pes[9:14]
                out.append(((b[0] >> 1) & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1)
        return out
    fh.seek(0)
    first = pts_list(fh.read(2 << 20))
    fh.seek(max(0, size - (8 << 20)))
    last = pts_list(fh.read(8 << 20))
    if not first or not last:
        return None
    secs = (max(last) - min(first)) / 90000
    return round(secs) if 0 < secs < 24 * 3600 else None


def header_duration(path):
    """Fallback length reader for files Windows can't measure (old .flv, some .mp4/.mov)."""
    import struct
    try:
        with open(path, 'rb') as fh:
            head = fh.read(4096)
            if head[0] == 0x47 and head[188] == 0x47:  # MPEG-TS (sometimes named .mp4)
                return ts_duration(fh, os.path.getsize(path))
            if head[:3] == b'FLV':
                i = head.find(b'duration')
                if i >= 0 and head[i + 8] == 0:  # AMF0 number
                    return round(struct.unpack('>d', head[i + 9:i + 17])[0]) or None
                return None
            # MP4/MOV: walk top-level boxes to 'moov', then find 'mvhd'
            fh.seek(0)
            size = os.path.getsize(path)
            pos = 0
            while pos < size:
                fh.seek(pos)
                hdr = fh.read(16)
                if len(hdr) < 8:
                    return None
                box_len, kind = struct.unpack('>I4s', hdr[:8])
                if box_len == 1:
                    box_len = struct.unpack('>Q', hdr[8:16])[0]
                elif box_len == 0:
                    box_len = size - pos
                if kind == b'moov':
                    moov = fh.read(min(box_len, 1 << 20)) if box_len > 16 else b''
                    fh.seek(pos + 8)
                    moov = fh.read(min(box_len - 8, 1 << 20))
                    i = moov.find(b'mvhd')
                    if i < 0:
                        return None
                    ver = moov[i + 4]
                    if ver == 1:
                        scale, dur = struct.unpack('>IQ', moov[i + 24:i + 36])
                    else:
                        scale, dur = struct.unpack('>II', moov[i + 16:i + 24])
                    return round(dur / scale) if scale else None
                if box_len < 8:
                    return None
                pos += box_len
    except (OSError, struct.error, IndexError):
        return None
    return None


def norm(s):
    s = unicodedata.normalize('NFKC', s)
    for a in '‘’“”':
        s = s.replace(a, "'")
    return s


def main():
    with open(os.path.join(HERE, 'catalog.json'), encoding='utf-8') as fh:
        cat = json.load(fh)
    positions = cat.pop('_positions')
    durations = {}
    dpath = os.path.join(HERE, 'durations.json')
    if os.path.exists(dpath):  # produced by get-durations.ps1
        with open(dpath, encoding='utf-8-sig') as fh:
            durations = {k: v.get('d') for k, v in json.load(fh).items()}
        for k, v in durations.items():
            if not v:
                durations[k] = header_duration(os.path.join(ROOT, *k.split('/')))
    cat = {norm(k): ({**v, 'same': norm(v['same'])} if 'same' in v else v) for k, v in cat.items()}
    used, courses, unmatched = set(), [], []
    for path, vids in units():
        entry = cat.get(norm(path))
        cover, docs = find_extras(path)
        if not vids and not docs:
            continue  # empty folder
        if entry is None:
            unmatched.append(path)
            name = path.split('/')[-1]
            entry = {'t': os.path.splitext(name)[0], 'i': '', 'g': '', 'p': ['uncategorised'],
                     's': 'Not catalogued yet. Add an entry for this folder to catalog.json and re-run build.py.'}
        used.add(norm(path))
        dup_of = None
        if 'same' in entry:
            dup_of = entry['same']
            base = dict(cat[dup_of])
            base['note'] = entry.get('note', 'duplicate copy')
            entry = base
        courses.append({
            'path': path, 't': entry['t'], 'i': entry.get('i', ''), 'g': entry.get('g', ''),
            'p': entry['p'], 's': entry['s'], 'note': entry.get('note', ''), 'dupOf': dup_of,
            'cover': cover, 'docs': docs,
            'videos': [{'f': f, 'b': b, 'd': durations.get(f)} for f, b in vids],
        })
    if unmatched:
        positions.append(['uncategorised', 'Uncategorised (new folders)'])
    out = 'window.LIBRARY = ' + json.dumps({'positions': positions, 'courses': courses}, ensure_ascii=False) + ';\n'
    with open(os.path.join(HERE, 'data.js'), 'w', encoding='utf-8') as fh:
        fh.write(out)
    stale = [k for k in cat if k not in used]
    nv = sum(len(c['videos']) for c in courses)
    nd = sum(1 for c in courses for v in c['videos'] if v['d'])
    print(f'{len(courses)} courses, {nv} videos written to data.js ({nd} with a length)')
    for u in unmatched: print('  NOT IN CATALOG:', u)
    for s in stale: print('  CATALOG ENTRY WITH NO FOLDER:', s)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
