#!/usr/bin/env python3
"""Member export (3514_<yyyymmdd>_<yyyymmdd>_statsExport.xlsx) -> tracker/names/<yyyy-mm-dd>.csv.

The export lists every governor in the kingdom with their current name, so the newest one is the
latest name per Governor ID (and adds governors below the TOP500 scan to the master list).
Only ID, name and power are kept: its kill points / kills cover the export's date range, not lifetime.

With --write it also records renames in tracker/accounts.csv (name = export name, old name appended
to previous_names), the same way build_week.py does.

Usage: .venv/bin/python import_export.py EXPORT_XLSX [--write]
"""
import argparse
import csv
import os
import re

import openpyxl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
ACCOUNTS = os.path.join(ROOT, 'tracker', 'accounts.csv')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    d = re.findall(r'(\d{4})(\d{2})(\d{2})', os.path.basename(args.export))[-1]  # end of the date range
    day = '-'.join(d)
    rows = list(openpyxl.load_workbook(args.export, read_only=True).active.iter_rows(values_only=True))
    head = [str(h).strip() if h is not None else '' for h in rows[0]]
    gi, ni, pi = head.index('Character ID'), head.index('Username'), head.index('Power')
    names = {}
    for r in rows[1:]:
        if r[gi] not in (None, ''):
            names[str(r[gi]).strip()] = (str(r[ni]).strip(), int(float(r[pi] or 0)))

    with open(ACCOUNTS, encoding='utf-8-sig') as f:
        rd = csv.DictReader(f)
        fields, accounts = rd.fieldnames, list(rd)
    renames = []
    for a in accounts:
        new = names.get(a['governor_id'], (None,))[0]
        if new and new != a['name']:
            renames.append((a['name'], new))
            prev = [n for n in a.get('previous_names', '').split(';') if n]
            if a['name'] not in prev:
                prev.append(a['name'])
            a.update(name=new, previous_names=';'.join(prev))
    for old, new in renames:
        print(f'rename: {old} -> {new}')

    if not args.write:
        print(f'{len(names)} governors, {len(renames)} rename(s) in accounts.csv. Rerun with --write to save.')
        return
    out = os.path.join(ROOT, 'tracker', 'names', f'{day}.csv')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'power'])
        w.writerows([gid, n, pw] for gid, (n, pw) in names.items())
    with open(ACCOUNTS, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(accounts)
    print(f'{len(names)} governors -> {os.path.relpath(out, ROOT)}; {len(renames)} rename(s) saved to accounts.csv')


if __name__ == '__main__':
    main()
