#!/usr/bin/env python3
"""Build tracker/mge/<start>.csv (one MGE's final ranking) from a transcribed ranking.

Input (pipe-separated, header row, one line per rank):
  ranking.txt   rank|name|points
Optional overrides.csv: name,governor_id  (screen name -> ID; empty governor_id keeps a name-only row)

Names are matched to Governor IDs in the newest member export (tracker/names/<date>.csv) and kingdom scan
(MGE is kingdom-wide, not just the alliance). The slots file tracker/mge/<start>_slots.csv is matched the same way.

Usage: .venv/bin/python import_mge.py START RANKING [--overrides FILE] [--write]
Without --write it only prints the checks.
"""
import argparse
import csv
import difflib
import os
import re
import sys
import unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
TRACKER = os.path.join(ROOT, 'tracker')


def norm(s):
    """Loose key: NFKC, no spaces, RoK decoration glyphs folded. Case is KEPT (Senopati != SenOpati)."""
    s = unicodedata.normalize('NFKC', s).replace(' ', '')
    for a, b in (('✕', 'x'), ('メ', 'x'), ('乂', 'x'), ('乄', 'x'), ('·', ''), ('٠', '')):
        s = s.replace(a, b)
    return s


def read(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def known_names():
    """{governor_id: name}: accounts, then the scan, then the member exports, newest last (newest name wins)."""
    names = {r['governor_id']: r['name'] for r in read(os.path.join(TRACKER, 'accounts.csv')) if r['governor_id']}
    for folder in ('scans', 'names'):
        d = os.path.join(TRACKER, folder)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv', f):
                names.update({r['governor_id']: r['name'] for r in read(os.path.join(d, f)) if r['governor_id']})
    return names


def matcher(names, overrides):
    """name -> (governor_id or '', note); note is '' for a sure match."""
    by_key = {}
    for gid, n in names.items():
        by_key.setdefault(norm(n), []).append(gid)

    def match(name):
        if name in overrides:
            return overrides[name], ''
        hit = by_key.get(norm(name), [])
        if len(hit) == 1:
            return hit[0], ''
        if len(hit) > 1:
            return '', f'?? ambiguous: {name} -> {[names[g] for g in hit]} (add to overrides)'
        close = [k for k in difflib.get_close_matches(norm(name), by_key, 3, 0.8) if len(by_key[k]) == 1]
        if close:
            gid = by_key[close[0]][0]
            return gid, f'~~ close match, please confirm: {name} -> {names[gid]} ({gid})'
        return '', f'-- not found (tracked by name only): {name}'
    return match


p = argparse.ArgumentParser()
p.add_argument('start')
p.add_argument('ranking')
p.add_argument('--overrides')
p.add_argument('--write', action='store_true')
a = p.parse_args()

rows = [(int(r['rank']), r['name'].strip(), int(r['points'].replace(',', '')))
        for r in csv.DictReader(open(a.ranking, encoding='utf-8'), delimiter='|')]
problems = 0
ranks = [r for r, _, _ in rows]
missing = sorted(set(range(1, max(ranks) + 1)) - set(ranks))
if missing:
    problems += 1
    print(f'!! missing ranks {missing}')
vals = [v for _, _, v in sorted(rows)]
if any(x < y for x, y in zip(vals, vals[1:])):
    problems += 1
    print('!! points not in descending order - check the reading')

overrides = {r['name']: r['governor_id'] for r in read(a.overrides)} if a.overrides else {}
names = known_names()
match = matcher(names, overrides)
out = []
for r, name, pts in sorted(rows):
    gid, note = match(name)
    if note:
        print(note)
        problems += note.startswith('??')
    out.append(dict(rank=r, governor_id=gid, name=names.get(gid, name) if gid else name, points=pts))
ids = [r['governor_id'] for r in out if r['governor_id']]
dup = {g for g in ids if ids.count(g) > 1}
if dup:
    problems += 1
    print(f'!! same ID matched to several names: {[(r["name"], r["governor_id"]) for r in out if r["governor_id"] in dup]}')

slots_path = os.path.join(TRACKER, 'mge', f'{a.start}_slots.csv')
slots = read(slots_path) if os.path.exists(slots_path) else []
for s in slots:
    if not s['governor_id']:
        gid, note = match(s['name'])
        print(f'slot {s["slot"]}: ' + (note or f'{s["name"]} -> {gid}'))
        s['governor_id'] = gid
if not slots:
    print(f'!! no slots file {slots_path}')
    problems += 1

print(f'{len(out)} players, {problems} blocking problem(s)')
if a.write:
    if problems:
        sys.exit('Not written: fix the blocking problems first.')
    for path, data in ((os.path.join(TRACKER, 'mge', f'{a.start}.csv'), out), (slots_path, slots)):
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    print(f'Wrote tracker/mge/{a.start}.csv and filled Governor IDs in the slots file')
