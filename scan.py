"""Scan the instructional library into course units. Shared by build.py."""
import os, re, json, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_EXT = {'.mp4', '.mkv', '.m4v', '.avi', '.flv', '.mov', '.webm', '.wmv'}
SKIP = {'_BJJ Library'}
# Folders whose immediate children are separate courses (relative paths, '/' separated)
COLLECTIONS = {
    '10th Planet Collection', '10th Planet Collection/10th Planet Freaks', '10th Planet Collection/10th Planet Pack',
    '10th Planet Collection/Brandon McCraghren', '10th Planet Collection/Eddie Bravo',
    'Craig Jones - COMPLETE Collection - as of  Oct 2023',
    'Craig Jones - COMPLETE Collection - as of  Oct 2023/Defense', 'Craig Jones - COMPLETE Collection - as of  Oct 2023/Guard Passing',
    'Craig Jones - COMPLETE Collection - as of  Oct 2023/Guards', 'Craig Jones - COMPLETE Collection - as of  Oct 2023/Leg Attacks',
    'Craig Jones - COMPLETE Collection - as of  Oct 2023/x_Other',
    'Gordon Ryan - COMPLETE Collection - as of Oct 2023',
    'Gordon Ryan - COMPLETE Collection - as of Oct 2023/My Evolution Your Revolution', 'Gordon Ryan - COMPLETE Collection - as of Oct 2023/Other',
    'Gordon Ryan - COMPLETE Collection - as of Oct 2023/Passing', 'Gordon Ryan - COMPLETE Collection - as of Oct 2023/Pillars Of Defense',
    'Gordon Ryan - COMPLETE Collection - as of Oct 2023/Systematically Attacking From___',
    'Gordon Ryan - COMPLETE Collection - as of Oct 2023/Systematically Attacking The___',
    'Garry Tonon', 'Jiu Jitsu For Old Guys Bundle By Bernardo Faria',
    'John Danaher - Ageless Jiu Jitsu - Complete PACK - 1080p 720p', 'John Danaher - Ageless Jiu Jitsu - Complete PACK - 1080p 720p/Gi',
    'John Danaher - Ageless Jiu Jitsu - Complete PACK - 1080p 720p/NoGi',
    'John Danaher - Ageless Jiu Jitsu - Complete PACK - 1080p 720p - Copy', 'John Danaher - Ageless Jiu Jitsu - Complete PACK - 1080p 720p - Copy/Gi',
    'John Danaher - collection 480p', 'John Danaher - collection 480p/Enter the System', 'John Danaher - collection 480p/Go Further Faster',
    'John Danaher - collection 480p/New Wave', 'John Danaher - collection 480p/Standing2Ground',
    'Lachlan Giles', 'Mikey Musumeci', 'Roger Gracie - The Guard System Bundle', 'Submeta',
    '720p - The Daisy Fresh Curriculum White Belt Bundle By Heath Pedigo', 'B Mac',
}

def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def videos_under(abs_dir):
    out = []
    for dp, dn, fn in os.walk(abs_dir):
        dn.sort(key=natural_key)
        for f in sorted(fn, key=natural_key):
            if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                p = os.path.join(dp, f)
                out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), os.path.getsize(p)))
    out.sort(key=lambda x: natural_key(x[0]))
    return out

def units():
    res = []
    def walk(rel):
        abs_dir = os.path.join(ROOT, rel) if rel else ROOT
        for name in sorted(os.listdir(abs_dir), key=natural_key):
            if not rel and name in SKIP: continue
            child = f'{rel}/{name}' if rel else name
            p = os.path.join(abs_dir, name)
            if os.path.isdir(p):
                if child in COLLECTIONS: walk(child)
                else: res.append((child, videos_under(p)))
            elif os.path.splitext(name)[1].lower() in VIDEO_EXT:
                res.append((child, [(child, os.path.getsize(p))]))
    walk('')
    return res

if __name__ == '__main__':
    for path, vids in units():
        print(f'{len(vids):4d} | {path}')
