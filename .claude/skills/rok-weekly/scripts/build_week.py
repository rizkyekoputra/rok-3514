#!/usr/bin/env python3
"""Build tracker/weeks/<monday>.csv from transcribed rankings and the member export.

Inputs (pipe-separated, header row, one line per rank):
  fort.txt   rank|name|forts
  tech.txt   rank|name|tech
Optional overrides.csv: name,governor_id  (screen name -> ID, for names the matcher can't resolve;
leave governor_id empty to keep a name-only account)

What it does:
  - checks both rankings have every rank 1..N and the same set of names
  - matches each screen name to a Governor ID in the export (exact, then a unique close match)
  - uses the export's spelling as the current name
  - adds new accounts to tracker/accounts.csv (farm if the name has "farm" or an F<number> suffix)
  - records renames in accounts.csv previous_names
  - prints everything that needs a human look

Usage: .venv/bin/python build_week.py MONDAY FORT TECH EXPORT_XLSX [--overrides FILE] [--write]
Without --write it only prints the checks.
"""
import argparse
import csv
import difflib
import os
import re
import sys
import unicodedata

import openpyxl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
TRACKER = os.path.join(ROOT, 'tracker')
FARM = re.compile(r'farm|\bF\d+\s*$', re.I)


def norm(s):
    """Loose key: NFKC, no spaces, RoK decoration glyphs folded. Case is KEPT (Senopati != SenOpati)."""
    s = unicodedata.normalize('NFKC', s).replace(' ', '')
    for a, b in (('✕', 'x'), ('メ', 'x'), ('乂', 'x'), ('乄', 'x'), ('·', ''), ('٠', '')):
        s = s.replace(a, b)
    return s


def read_rank(path, col):
    rows = list(csv.DictReader(open(path, encoding='utf-8'), delimiter='|'))
    return [(int(r['rank']), r['name'].strip(), int(r[col].replace(',', ''))) for r in rows]


p = argparse.ArgumentParser()
p.add_argument('monday')
p.add_argument('fort')
p.add_argument('tech')
p.add_argument('export')
p.add_argument('--overrides')
p.add_argument('--write', action='store_true')
a = p.parse_args()

fort, tech = read_rank(a.fort, 'forts'), read_rank(a.tech, 'tech')
problems = 0
for label, rows in (('fort', fort), ('tech', tech)):
    ranks = [r for r, _, _ in rows]
    missing = sorted(set(range(1, max(ranks) + 1)) - set(ranks))
    if missing:
        problems += 1
        print(f'!! {label}: missing ranks {missing}')
    vals = [v for _, _, v in sorted(rows)]
    if any(x < y for x, y in zip(vals, vals[1:])):
        problems += 1
        print(f'!! {label}: values not in descending order - check the reading')
fn, tn = {n for _, n, _ in fort}, {n for _, n, _ in tech}
if fn != tn:
    problems += 1
    print(f'!! names only in fort: {sorted(fn - tn)}\n!! names only in tech: {sorted(tn - fn)}')

ws = openpyxl.load_workbook(a.export, read_only=True, data_only=True).worksheets[0]
export = {str(r[0]): str(r[1]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}
by_key = {}
for gid, name in export.items():
    by_key.setdefault(norm(name), []).append(gid)
overrides = {}
if a.overrides:
    overrides = {r['name']: r['governor_id'] for r in csv.DictReader(open(a.overrides, encoding='utf-8'))}

ids, used = {}, set()
for name in sorted(fn | tn):
    if name in overrides:
        ids[name] = overrides[name]
        continue
    hit = by_key.get(norm(name), [])
    if len(hit) == 1:
        ids[name] = hit[0]
    elif len(hit) > 1:
        print(f'?? ambiguous: {name} -> {[export[g] for g in hit]} (add to overrides)')
        problems += 1
for name in sorted(fn | tn):
    if name in ids:
        used.add(ids[name])
for name in sorted(fn | tn):
    if name in ids or name in overrides:
        continue
    close = [k for k in difflib.get_close_matches(norm(name), by_key, 3, 0.8)
             if len(by_key[k]) == 1 and by_key[k][0] not in used]
    if close:
        gid = by_key[close[0]][0]
        ids[name] = gid
        used.add(gid)
        print(f'~~ close match, please confirm: {name} -> {export[gid]} ({gid})')
    else:
        ids[name] = ''
        print(f'-- not in export (tracked by name only): {name}')

dup = {g for g in ids.values() if g and list(ids.values()).count(g) > 1}
if dup:
    problems += 1
    print(f'!! same ID matched to several names: {[(n, g) for n, g in ids.items() if g in dup]}')

tech_by = {n: (r, v) for r, n, v in tech}
rows = []
for r, name, f in sorted(fort):
    gid = ids.get(name, '')
    tr, tv = tech_by.get(name, ('', ''))
    rows.append(dict(governor_id=gid, name=export.get(gid, name) if gid else name,
                     fort_rank=r, forts=f, tech_rank=tr, tech=tv))

acc_path = os.path.join(TRACKER, 'accounts.csv')
acc = list(csv.DictReader(open(acc_path, encoding='utf-8-sig')))
fields = ['governor_id', 'name', 'type', 'role', 'confirmed', 'previous_names']
for x in acc:
    for k in fields:
        x.setdefault(k, '')
by_id = {x['governor_id']: x for x in acc if x['governor_id']}
by_name = {x['name']: x for x in acc if not x['governor_id']}
new = []
for row in rows:
    x = by_id.get(row['governor_id']) if row['governor_id'] else by_name.get(row['name'])
    if x:
        if x['name'] != row['name']:
            print(f'>> renamed: {x["name"]} -> {row["name"]} ({x["type"]}{", " + x["role"] if x["role"] else ""})')
            x['previous_names'] = ';'.join(filter(None, [x['previous_names'], x['name']]))
            x['name'] = row['name']
    else:
        farm = bool(FARM.search(row['name']))
        x = dict(governor_id=row['governor_id'], name=row['name'], type='farm' if farm else 'main',
                 role='', confirmed='yes' if farm else 'no', previous_names='')
        acc.append(x)
        new.append(x)
        (by_id if x['governor_id'] else by_name)[x['governor_id'] or x['name']] = x
if new:
    print(f'++ new accounts: farms {[x["name"] for x in new if x["type"] == "farm"]}')
    print(f'++ new accounts treated as MAIN until confirmed: {[x["name"] for x in new if x["type"] == "main"]}')
seen = {r['governor_id'] for r in rows if r['governor_id']} | {r['name'] for r in rows if not r['governor_id']}
prev = sorted(f for f in os.listdir(os.path.join(TRACKER, 'weeks')) if f < a.monday)
if prev:
    last = list(csv.DictReader(open(os.path.join(TRACKER, 'weeks', prev[-1]), encoding='utf-8-sig')))
    gone = [r['name'] for r in last if (r['governor_id'] or r['name']) not in seen]
    if gone:
        print(f'<< in {prev[-1][:-4]} but not this week: {gone}')

print(f'{len(rows)} players, {problems} blocking problem(s)')
if a.write:
    if problems:
        sys.exit('Not written: fix the blocking problems first.')
    out = os.path.join(TRACKER, 'weeks', f'{a.monday}.csv')
    with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(acc_path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(acc)
    print(f'Wrote {out} and updated accounts.csv')
