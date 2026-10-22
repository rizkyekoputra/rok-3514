#!/usr/bin/env python3
"""Convert a kingdom scan (TOP500-<yyyy-mm-dd>-….xlsx) to tracker/scans/<yyyy-mm-dd>.csv.

The newest scan file is the master player list: every governor in it with their current alliance.
track.py reads only these CSVs (no openpyxl needed there or in the GitHub Action).

Usage: .venv/bin/python import_scan.py SCAN_XLSX [--date YYYY-MM-DD]
The date defaults to the first yyyy-mm-dd in the file name.
"""
import argparse
import csv
import os
import re

import openpyxl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
COLS = [('governor_id', 'ID'), ('name', 'Name'), ('power', 'Power'), ('killpoints', 'Killpoints'),
        ('deads', 'Deads'), ('t4_kills', 'T4 Kills'), ('t5_kills', 'T5 Kills'), ('rss_gathered', 'Rss Gathered'),
        ('rss_assistance', 'Rss Assistance'), ('helps', 'Helps'), ('alliance', 'Alliance')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scan')
    ap.add_argument('--date')
    args = ap.parse_args()
    day = args.date or re.search(r'\d{4}-\d{2}-\d{2}', os.path.basename(args.scan)).group(0)
    rows = list(openpyxl.load_workbook(args.scan, read_only=True).active.iter_rows(values_only=True))
    head = [str(h).strip() if h is not None else '' for h in rows[0]]
    missing = [src for _, src in COLS if src not in head]
    if missing:
        raise SystemExit(f'Scan is missing columns: {missing}')
    idx = {src: head.index(src) for _, src in COLS}
    out = os.path.join(ROOT, 'tracker', 'scans', f'{day}.csv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = 0
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow([c for c, _ in COLS])
        for r in rows[1:]:
            if r[idx['ID']] is None:
                continue
            vals = []
            for c, src in COLS:
                v = r[idx[src]]
                if c in ('governor_id', 'name', 'alliance'):
                    vals.append(str(v).strip() if v is not None else '')
                else:
                    vals.append(max(0, int(float(v))) if v not in (None, '') else '')
            w.writerow(vals)
            n += 1
    print(f'{n} governors -> {os.path.relpath(out, ROOT)}')


if __name__ == '__main__':
    main()
