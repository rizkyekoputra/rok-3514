#!/usr/bin/env python3
"""Build tracker/canyon/<start>.csv (one Canyon Clash's combat statistics) from a transcribed list.

Input (CSV, header row, one line per governor in screen order):
  list.csv      rank,name,defenses,attacks   (attacks = attacks used out of 3)
Optional overrides.csv: name,governor_id  (screen name -> ID; empty governor_id keeps a name-only row)

Names are matched to Governor IDs the same way as import_mge.py (accounts, scans, member exports).

Usage: .venv/bin/python import_canyon.py START LIST [--overrides FILE] [--write]
Without --write it only prints the checks.
"""
import argparse
import csv
import os
import sys

from match_names import TRACKER, known_names, matcher, read

ATTACKS = 3


p = argparse.ArgumentParser()
p.add_argument('start')
p.add_argument('list')
p.add_argument('--overrides')
p.add_argument('--write', action='store_true')
a = p.parse_args()

rows = [(int(r['rank']), r['name'].strip(), int(r['defenses']), int(r['attacks'])) for r in read(a.list)]
problems = 0
ranks = [r[0] for r in rows]
missing = sorted(set(range(1, max(ranks) + 1)) - set(ranks))
if missing:
    problems += 1
    print(f'!! missing ranks {missing}')
bad = [r[1] for r in rows if not 0 <= r[3] <= ATTACKS]
if bad:
    problems += 1
    print(f'!! attacks outside 0-{ATTACKS}: {bad}')

overrides = {r['name']: r['governor_id'] for r in read(a.overrides)} if a.overrides else {}
names = known_names()
match = matcher(names, overrides)
out = []
for r, name, dfn, att in sorted(rows):
    gid, note = match(name)
    if note:
        print(note)
        problems += note.startswith('??')
    out.append(dict(rank=r, governor_id=gid, name=names.get(gid, name) if gid else name, defenses=dfn, attacks=att))
ids = [r['governor_id'] for r in out if r['governor_id']]
dup = {g for g in ids if ids.count(g) > 1}
if dup:
    problems += 1
    print(f'!! same ID matched to several names: {[(r["name"], r["governor_id"]) for r in out if r["governor_id"] in dup]}')

print(f'{len(out)} players, {sum(r["attacks"] == ATTACKS for r in out)} used all {ATTACKS} attacks, '
      f'{problems} blocking problem(s)')
if a.write:
    if problems:
        sys.exit('Not written: fix the blocking problems first.')
    path = os.path.join(TRACKER, 'canyon', f'{a.start}.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f'Wrote tracker/canyon/{a.start}.csv')
