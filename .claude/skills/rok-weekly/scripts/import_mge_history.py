#!/usr/bin/env python3
"""Build tracker/mge/history.csv (the in-game "History's Mightiest Governors": top 10 of each past MGE season).

Input (pipe-separated, header row, one line per rank; alliance tag without brackets, blank when none):
  history.txt   season|date|rank|alliance|name|points
Optional overrides.csv: name,governor_id  (screen name -> ID; empty governor_id keeps a name-only row)

Past seasons show the name a governor had then, so names are matched against every name ever seen (accounts and
their previous names, week files, scans, member exports, KvK name lists, MGE rankings), not just the current one.
Seasons already in the file are replaced, others kept, so newer recordings can be added later.

Usage: .venv/bin/python import_mge_history.py HISTORY [--overrides FILE] [--write]
Without --write it only prints the checks.
"""
import argparse
import csv
import difflib
import os
import sys

from match_names import TRACKER, norm, read

FIELDS = ['season', 'date', 'rank', 'alliance', 'name', 'points', 'governor_id']


def all_names():
    """{name: {governor_id, ...}} for every name any source has recorded."""
    seen = {}
    def add(gid, name):
        if gid and name:
            seen.setdefault(name, set()).add(gid)
    for r in read(os.path.join(TRACKER, 'accounts.csv')):
        for n in [r['name']] + r['previous_names'].split(';'):
            add(r['governor_id'], n)
    for folder in ('weeks', 'scans', 'names', 'ch', 'mge'):
        d = os.path.join(TRACKER, folder)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith('.csv') and f[:1].isdigit() and not f.endswith('_slots.csv'):
                for r in read(os.path.join(d, f)):
                    add(r.get('governor_id'), r.get('name'))
    return seen


p = argparse.ArgumentParser()
p.add_argument('history')
p.add_argument('--overrides')
p.add_argument('--write', action='store_true')
a = p.parse_args()

rows = [dict(season=int(r['season']), date=r['date'].strip(), rank=int(r['rank']), alliance=r['alliance'].strip(),
             name=r['name'].strip(), points=int(r['points'].replace(',', '')))
        for r in csv.DictReader(open(a.history, encoding='utf-8'), delimiter='|')]
problems = 0
for s in sorted({r['season'] for r in rows}):
    rs = sorted((r for r in rows if r['season'] == s), key=lambda r: r['rank'])
    if [r['rank'] for r in rs] != list(range(1, len(rs) + 1)) or len({r['date'] for r in rs}) != 1:
        problems += 1
        print(f'!! season {s}: ranks {[r["rank"] for r in rs]}, dates {sorted({r["date"] for r in rs})}')
    if any(x['points'] < y['points'] for x, y in zip(rs, rs[1:])):
        problems += 1
        print(f'!! season {s}: points not in descending order - check the reading')

overrides = {r['name']: r['governor_id'] for r in read(a.overrides)} if a.overrides else {}
by_key = {}
for name, gids in all_names().items():
    by_key.setdefault(norm(name), set()).update(gids)
for r in rows:
    if r['name'] in overrides:
        r['governor_id'] = overrides[r['name']]
        continue
    hit = by_key.get(norm(r['name']), set())
    r['governor_id'] = next(iter(hit)) if len(hit) == 1 else ''
    if len(hit) > 1:
        problems += 1
        print(f'?? ambiguous: {r["name"]} (season {r["season"]}) -> {sorted(hit)} (add to overrides)')
    elif not hit:
        close = [k for k in difflib.get_close_matches(norm(r['name']), by_key, 3, 0.8) if len(by_key[k]) == 1]
        print(f'-- not found (name only): {r["name"]} (season {r["season"]})' +
              (f'; close: {close[0]} -> {next(iter(by_key[close[0]]))}, confirm with overrides' if close else ''))
for s in sorted({r['season'] for r in rows}):
    ids = [r['governor_id'] for r in rows if r['season'] == s and r['governor_id']]
    dup = {g for g in ids if ids.count(g) > 1}
    if dup:
        problems += 1
        print(f'!! season {s}: same ID for several names: {[(r["name"], r["governor_id"]) for r in rows if r["season"] == s and r["governor_id"] in dup]}')

matched = sum(bool(r['governor_id']) for r in rows)
print(f'{len(rows)} rows in {len({r["season"] for r in rows})} seasons, {matched} matched to an ID, {problems} blocking problem(s)')
if a.write:
    if problems:
        sys.exit('Not written: fix the blocking problems first.')
    path = os.path.join(TRACKER, 'mge', 'history.csv')
    new = {r['season'] for r in rows}
    keep = [r for r in read(path) if int(r['season']) not in new] if os.path.exists(path) else []
    out = sorted(keep + rows, key=lambda r: (-int(r['season']), int(r['rank'])))
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f'Wrote tracker/mge/history.csv ({len(out)} rows)')
