#!/usr/bin/env python3
"""In-game Immigration Log (kingdom -> Immigration Log) -> tracker/immigration.csv.

Input: a pipe file transcribed from the recording, one row per line, newest first as in game:
    date|time UTC|out/in|name|special
(date = the "UTC yyyy/mm/dd" header above the row; out = "emigrated out of the kingdom", in = "entered the kingdom
via same-season immigration"; special = "special" for "same-season special immigration"). Lines starting with # are skipped.

Names are matched to Governor IDs against every name a governor ever had (accounts, scans, member exports, week
files, KvK lists). A default name with the ID in it (Governor123…, Gubernur123…, Thống đốc123…) gives the ID directly.
Rows already in immigration.csv (same date, time, name) are kept once, so overlapping recordings can be imported.

Usage: python3 import_immigration.py LOG.txt [--overrides overrides.csv] [--write]
       overrides.csv: name,governor_id (empty ID = keep it name-only)
"""
import argparse
import csv
import os
import re

from match_names import TRACKER, norm, read

OUT = os.path.join(TRACKER, 'immigration.csv')
FIELDS = ['date', 'time', 'direction', 'name', 'special', 'governor_id']


def all_names():
    """{norm(name): {governor_id}} over every name file the tracker has."""
    by = {}
    def add(gid, name):
        if gid and name:
            by.setdefault(norm(name), set()).add(gid)
    for r in read(os.path.join(TRACKER, 'accounts.csv')):
        add(r['governor_id'], r['name'])
        for n in (r.get('previous_names') or '').split(';'):
            add(r['governor_id'], n)
    for folder in ('scans', 'names', 'weeks', 'ch'):
        d = os.path.join(TRACKER, folder)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith('.csv'):
                for r in read(os.path.join(d, f)):
                    add(r.get('governor_id', ''), r.get('name', ''))
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--overrides')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    over = {r['name']: r['governor_id'] for r in read(args.overrides)} if args.overrides else {}
    by = all_names()
    rows = []
    for line in open(args.log, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'):
            continue
        d, t, direction, name, special = (line.split('|') + [''] * 5)[:5]
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', d) or direction not in ('in', 'out'):
            print(f'!! bad line: {line}')
            continue
        if name in over:
            gid, note = over[name], ''
        else:
            hit = by.get(norm(name), set())
            m = re.search(r'(\d{6,})$', name)
            if m and not hit:
                gid, note = m.group(1), ''
            elif len(hit) == 1:
                gid, note = next(iter(hit)), ''
            elif hit:
                gid, note = '', f'?? ambiguous: {name} -> {sorted(hit)} (add to overrides)'
            else:
                gid, note = '', f'-- not found (name only): {name}'
        if note:
            print(note)
        rows.append(dict(date=d, time=t, direction=direction, name=name, special='yes' if special else '', governor_id=gid))

    old = read(OUT) if os.path.exists(OUT) else []
    seen = {(r['date'], r['time'], r['name']) for r in rows}
    merged = rows + [r for r in old if (r['date'], r['time'], r['name']) not in seen]
    merged.sort(key=lambda r: (r['date'], r['time']), reverse=True)
    n_in = sum(r['direction'] == 'in' for r in rows)
    print(f'{len(rows)} rows ({len(rows) - n_in} out, {n_in} in), {sum(1 for r in rows if r["governor_id"])} matched; '
          f'{len(merged)} in immigration.csv after merge')
    if not args.write:
        print('Rerun with --write to save.')
        return
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(merged)
    print(f'-> {os.path.relpath(OUT, os.path.dirname(TRACKER))}')


if __name__ == '__main__':
    main()
