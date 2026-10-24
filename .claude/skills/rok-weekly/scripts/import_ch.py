#!/usr/bin/env python3
"""City hall levels -> tracker/ch/<yyyy-mm-dd>.csv (governor_id, name, ch).

Reads every sheet of an xlsx (or one csv) with a Governor ID column. The level comes from a "City Hall" / "CH" column
when the sheet has one, else from --ch (e.g. a CH25 roster, where every listed governor is CH25).
City hall levels never go down, so the dashboard keeps the highest level seen for each governor across all files.

Usage: .venv/bin/python import_ch.py FILE --date YYYY-MM-DD [--ch 25] [--write]
Without --write it only prints what it found.
"""
import argparse
import csv
import os
import re

import openpyxl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
OUT = os.path.join(ROOT, 'tracker', 'ch')

p = argparse.ArgumentParser()
p.add_argument('file')
p.add_argument('--date', required=True)
p.add_argument('--ch', type=int, help='level for every listed governor when the sheet has no city hall column')
p.add_argument('--write', action='store_true')
a = p.parse_args()


def sheets(path):
    if path.lower().endswith('.csv'):
        with open(path, encoding='utf-8-sig') as f:
            yield os.path.basename(path), list(csv.reader(f))
        return
    for ws in openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets:
        yield ws.title, [[('' if c is None else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]


found = {}  # governor_id -> [name, ch]
for title, rows in sheets(a.file):
    if not rows:
        continue
    head = [h.strip().lower() for h in rows[0]]
    gid = next((i for i, h in enumerate(head) if h in ('governor id', 'character id', 'id', 'governor_id')), None)
    name = next((i for i, h in enumerate(head) if 'name' in h), None)
    lvl = next((i for i, h in enumerate(head) if h in ('ch', 'city hall', 'cityhall', 'city hall level', 'ch level')), None)
    if gid is None or (lvl is None and a.ch is None):
        print(f'-- {title}: skipped (no Governor ID column{"" if gid is None else ", no city hall column and no --ch"})')
        continue
    n = 0
    for r in rows[1:]:
        g = re.sub(r'\.0$', '', r[gid].strip()) if gid < len(r) else ''
        if not g.isdigit():
            continue
        ch = int(float(r[lvl])) if lvl is not None and lvl < len(r) and r[lvl].strip() else a.ch
        if ch is None:
            continue
        old = found.get(g, ['', 0])
        found[g] = [(r[name].strip() if name is not None and name < len(r) else '') or old[0], max(ch, old[1])]
        n += 1
    print(f'{title}: {n} governors')

levels = {}
for _, ch in found.values():
    levels[ch] = levels.get(ch, 0) + 1
print(f'{len(found)} governors in total; by level: ' + ', '.join(f'CH{k}: {v}' for k, v in sorted(levels.items(), reverse=True)))
if a.write:
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f'{a.date}.csv')
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'ch'])
        w.writerows([g, n, ch] for g, (n, ch) in sorted(found.items()))
    print(f'Wrote {out}')
