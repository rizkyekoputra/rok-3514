#!/usr/bin/env python3
"""Import one KvK's tracking sheet into tracker/kvk/ and seed name history from it.

Every KvK sheet has its own layout; this recognises them by their headers and keeps what each one has:
  KP sheets     (KvK 4, 6, 7)  KP gained vs a target, KP %, fines, MIGRATED/ZEROED, deads when present
  DKP sheet     (KvK 8)        DKP gained vs target, DKP %
  Acclaim sheets(KvK 9, 10)    acclaim (vs target acclaim when present), status; several scans -> first/last
Older KvKs have no acclaim (it was added to the game later), newer ones no KP target; missing = blank.

Writes
  tracker/kvk/kvk<N>.csv           governor_id, name, type, power, metric, value, target, pct, deads, acclaim, status, fine
  tracker/kvk/kvks.csv             kvk, date, estimated, metric, source  (one row per KvK, updated in place)
  tracker/names/<date>_kvk<N>.csv  names as they were in that KvK (one file per scan date when the sheet has scans)

Usage: python3 import_kvk.py N LINK_OR_CSV --date YYYY-MM-DD [--estimated]
  --date  the day the KvK ended (or its last scan); --estimated marks it as a guess on the dashboard
"""
import argparse
import csv
import io
import os
import re
import urllib.request
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
KVK = os.path.join(ROOT, 'tracker', 'kvk')
OUT = ['governor_id', 'name', 'type', 'power', 'metric', 'value', 'target', 'pct', 'deads', 'acclaim', 'status', 'fine']


def fetch(src):
    m = re.search(r'docs\.google\.com/spreadsheets/d/([\w-]+)', src)
    if not m:
        with open(src, encoding='utf-8-sig') as f:
            return f.read()
    gid = re.search(r'[#&?]gid=(\d+)', src)
    url = f'https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv' + (f'&gid={gid.group(1)}' if gid else '')
    with urllib.request.urlopen(url, timeout=90) as r:
        if 'text/csv' not in r.headers.get('Content-Type', ''):
            raise SystemExit('Not a CSV: is the sheet shared as "anyone with the link"?')
        return r.read().decode('utf-8-sig')


def num(v):
    """'1,234,567' -> 1234567; '45,7' / '1366.05%' -> 45.7 / 1366.05; blank or junk -> None."""
    v = (v or '').strip().replace('%', '').replace(' ', '')
    if re.fullmatch(r'-?\d+,\d{1,2}', v):  # decimal comma
        v = v.replace(',', '.')
    v = v.replace(',', '')
    try:
        f = float(v)
    except ValueError:
        return None
    return int(f) if f.is_integer() else round(f, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kvk', type=int)
    ap.add_argument('source')
    ap.add_argument('--date', required=True)
    ap.add_argument('--estimated', action='store_true')
    args = ap.parse_args()
    rows = list(csv.reader(io.StringIO(fetch(args.source))))
    head = [re.sub(r'\s+', ' ', h).strip() for h in rows[0]]
    col = lambda *names: next((head.index(n) for n in names if n in head), None)
    get = lambda r, i: r[i].strip() if i is not None and i < len(r) else ''

    gi, ni = col('ID', 'Character ID', 'Governor ID'), col('Name', 'Username', 'Governor Name')
    if gi is None or ni is None:
        raise SystemExit(f'No ID/name column: {head}')
    ti, si, scan = col('Type'), col('Slot', 'SLOT'), col('Last Scan')
    pw = col('Starting Power First Snapshot', 'Initial Power', 'Power', 'Current Power')
    fine, fstat, stat = col('GOLD FINE', 'FINE GOLD'), col('Fine Status'), col('Status')
    dead, accl = col('Total #deadtroops'), col('Aclaim', 'Acclaim')
    if col('DKP Achievement') is not None:
        metric, vi, tgi, pi = 'DKP', col('DKP Achievement'), col('Target KP'), col('DKP%')
    elif col('Target Acclaim') is not None:
        metric, vi, tgi, pi = 'Acclaim', accl, col('Initial Target', 'Target Acclaim'), col('Acclaim Progress %')
    elif col('Total KP') is not None:
        metric, vi, tgi, pi = 'KP', col('Total KP'), col('KP Required', 'Target KP (50% of power)'), col('KP %')
    elif col('Last Scan Final') is not None:  # KvK 7: target was 100% of power (KP % = KP / power)
        metric, vi, tgi, pi = 'KP', col('Last Scan Final'), None, col('KP %')
    elif accl is not None:
        metric, vi, tgi, pi = 'Acclaim', accl, None, None
    else:
        raise SystemExit(f'Unknown KvK layout: {head}')

    # one record per governor; with several scans, results from the last scan and power from the first
    by_id, names_at = {}, {}
    for r in rows[1:]:
        gid = get(r, gi).replace(',', '')
        if not gid.isdigit():
            continue
        when = datetime.strptime(get(r, scan)[:10], '%d/%m/%Y').date().isoformat() if scan is not None and get(r, scan) else args.date
        names_at.setdefault(when, {})[gid] = get(r, ni)
        by_id.setdefault(gid, []).append((when, r))
    out = []
    for gid, recs in by_id.items():
        recs.sort(key=lambda x: x[0])
        first, last = recs[0][1], recs[-1][1]
        value = num(get(last, vi))
        if metric == 'KP' and col('Last Scan Final') is not None and not value:
            value = num(get(last, col('Total')))
        power = num(get(first, pw))
        target = num(get(first, tgi)) if tgi is not None else (power if col('Last Scan Final') is not None else None)
        pct = num(get(last, pi)) if pi is not None else None
        if pct is None and value is not None and target:
            pct = round(100 * value / target, 2)
        status = ' · '.join(x for x in (get(last, fstat), get(last, stat),
                                        'Vacation' if get(last, si).lower() == 'vacation' else '') if x)
        out.append([gid, get(last, ni), get(last, ti).lower(), power, metric, value, target, pct,
                    num(get(last, dead)), num(get(last, accl)) if accl is not None else None, status,
                    num(get(last, fine))])

    os.makedirs(KVK, exist_ok=True)
    with open(os.path.join(KVK, f'kvk{args.kvk}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(OUT)
        w.writerows(['' if v is None else v for v in r] for r in out)
    meta_path = os.path.join(KVK, 'kvks.csv')
    meta = []
    if os.path.exists(meta_path):
        with open(meta_path, encoding='utf-8-sig') as f:
            meta = [m for m in csv.DictReader(f) if m['kvk'] != str(args.kvk)]
    meta.append(dict(kvk=args.kvk, date=args.date, estimated='yes' if args.estimated else '', metric=metric,
                     source=re.sub(r'[?#].*', '', args.source)))
    meta.sort(key=lambda m: int(m['kvk']))
    with open(meta_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['kvk', 'date', 'estimated', 'metric', 'source'])
        w.writeheader()
        w.writerows(meta)

    ndir = os.path.join(ROOT, 'tracker', 'names')
    os.makedirs(ndir, exist_ok=True)
    for f in os.listdir(ndir):  # replace this KvK's earlier name files
        if f.endswith(f'_kvk{args.kvk}.csv'):
            os.remove(os.path.join(ndir, f))
    for when, names in names_at.items():
        with open(os.path.join(ndir, f'{when}_kvk{args.kvk}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['governor_id', 'name', 'power'])
            w.writerows([g, n, ''] for g, n in names.items())
    print(f'KvK {args.kvk}: {len(out)} governors, metric {metric}, name lists for {sorted(names_at)}')


if __name__ == '__main__':
    main()
