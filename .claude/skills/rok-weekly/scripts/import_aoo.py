#!/usr/bin/env python3
"""Build tracker/aoo/<date>.csv (one Ark of Osiris battle's individual ranking) from a transcribed list.

Input (CSV, header row, one line per registered governor in screen order):
  list.csv      rank,name,points,kills   (blank points = "Did Not Participate"; kills = the sword column)
Optional overrides.csv: name,governor_id  (screen name -> ID; empty governor_id keeps a name-only row)

Names are matched to Governor IDs the same way as import_mge.py (accounts, scans, member exports).

Usage: .venv/bin/python import_aoo.py DATE LIST [--overrides FILE] [--write]
Without --write it only prints the checks.
"""
import argparse
import csv
import os
import sys

from match_names import TRACKER, known_names, matcher, read

p = argparse.ArgumentParser()
p.add_argument('date')
p.add_argument('list')
p.add_argument('--overrides')
p.add_argument('--write', action='store_true')
a = p.parse_args()

rows = [(int(r['rank']), r['name'].strip(), int(r['points'] or 0), int(r['kills'] or 0)) for r in read(a.list)]
problems = 0
ranks = [r[0] for r in rows]
missing = sorted(set(range(1, max(ranks) + 1)) - set(ranks))
if missing:
    problems += 1
    print(f'!! missing ranks {missing}')
vals = [r[2] for r in sorted(rows)]
if any(x < y for x, y in zip(vals, vals[1:])):
    problems += 1
    print('!! points not in descending order - check the reading')

overrides = {r['name']: r['governor_id'] for r in read(a.overrides)} if a.overrides else {}
names = known_names()
match = matcher(names, overrides)
out = []
for r, name, pts, kills in sorted(rows):
    gid, note = match(name)
    if note:
        print(note)
        problems += note.startswith('??')
    out.append(dict(rank=r, governor_id=gid, name=names.get(gid, name) if gid else name, points=pts, kills=kills))
ids = [r['governor_id'] for r in out if r['governor_id']]
dup = {g for g in ids if ids.count(g) > 1}
if dup:
    problems += 1
    print(f'!! same ID matched to several names: {[(r["name"], r["governor_id"]) for r in out if r["governor_id"] in dup]}')

print(f'{len(out)} registered, {sum(not r["points"] for r in out)} did not participate, {problems} blocking problem(s)')
if a.write:
    if problems:
        sys.exit('Not written: fix the blocking problems first.')
    path = os.path.join(TRACKER, 'aoo', f'{a.date}.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f'Wrote tracker/aoo/{a.date}.csv')
