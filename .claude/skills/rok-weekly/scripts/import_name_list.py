#!/usr/bin/env python3
"""Seed name history from an old list of governors: Google Sheets link (shared "anyone with the link") or CSV.

Finds the Governor ID column (header "ID", "Governor ID" or "Character ID") and the name column ("Name",
"Username", "Governor Name"), and writes tracker/names/<date>.csv. track.py then shows those names, matched
by ID, in each player's Name history. A list older than the newest names file never renames anyone.

Usage: python3 import_name_list.py SOURCE --date YYYY-MM-DD [--label TEXT]
  SOURCE  https://docs.google.com/spreadsheets/d/<id>/edit?gid=<gid>  (that tab is read), or a .csv path
  --date  the day the names were current (e.g. the end of the period the sheet covers)
"""
import argparse
import csv
import io
import os
import re
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
ID_COLS = ('id', 'governor id', 'character id', 'gov id')
NAME_COLS = ('name', 'username', 'governor name', 'governor')


def fetch(src):
    m = re.search(r'docs\.google\.com/spreadsheets/d/([\w-]+)', src)
    if not m:
        with open(src, encoding='utf-8-sig') as f:
            return f.read()
    gid = re.search(r'[#&?]gid=(\d+)', src)
    url = f'https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv' + (f'&gid={gid.group(1)}' if gid else '')
    with urllib.request.urlopen(url, timeout=60) as r:
        if 'text/csv' not in r.headers.get('Content-Type', ''):
            raise SystemExit('Not a CSV: is the sheet shared as "anyone with the link"?')
        return r.read().decode('utf-8-sig')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('--date', required=True)
    args = ap.parse_args()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', args.date):
        raise SystemExit('--date must be YYYY-MM-DD')
    rows = list(csv.reader(io.StringIO(fetch(args.source))))
    head = [re.sub(r'\s+', ' ', h).strip().lower() for h in rows[0]]
    gi = next((head.index(c) for c in ID_COLS if c in head), None)
    ni = next((head.index(c) for c in NAME_COLS if c in head), None)
    if gi is None or ni is None:
        raise SystemExit(f'No ID/name column in header: {rows[0]}')
    names = {}
    for r in rows[1:]:
        gid, name = (r[gi].strip().replace(',', '') if len(r) > gi else ''), (r[ni].strip() if len(r) > ni else '')
        if gid.isdigit() and name:
            names[gid] = name
    out = os.path.join(ROOT, 'tracker', 'names', f'{args.date}.csv')
    if os.path.exists(out):
        with open(out, encoding='utf-8-sig') as f:  # same day from another list: keep both, this one wins on conflicts
            for r in csv.DictReader(f):
                names.setdefault(r['governor_id'], r['name'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'power'])
        w.writerows([g, n, ''] for g, n in names.items())
    print(f'{len(names)} governors -> {os.path.relpath(out, ROOT)}')


if __name__ == '__main__':
    main()
