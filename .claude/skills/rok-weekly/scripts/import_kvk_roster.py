#!/usr/bin/env python3
"""KvK battle roster (Lost Kingdom Battle Roster screen) -> tracker/kvk/kvk<N>_roster.csv.

Input: pipe file transcribed from the roster recording, one governor per line:
    alliance|rank|name|power
(alliance = "[TAG]Name" as shown, or "No alliance"; rank = Leader, R4, R3, R2, R1, blank for No alliance;
power = the roster's power, digits only). Lines starting with # are skipped.

Matching: by name against every name a governor ever had (as import_immigration.py), then confirmed or
found by power: the latest member export's power for that ID should be within POWER_TOL. A name that is
not found falls back to the closest power in the latest export if one is within POWER_TOL and the
names are similar. Check `~~` lines by hand; put corrections in --overrides (name,governor_id).

Usage: python3 import_kvk_roster.py N ROSTER.txt --date YYYY-MM-DD [--overrides overrides.csv] [--write]
"""
import argparse
import csv
import difflib
import os
import re

from import_immigration import all_names
from match_names import TRACKER, norm, read

POWER_TOL = 0.03  # roster power vs the latest member export


def latest_export():
    d = os.path.join(TRACKER, 'names')
    day = sorted(f for f in os.listdir(d) if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv', f))[-1]
    return day[:-4], {r['governor_id']: (r['name'], int(r['power'] or 0)) for r in read(os.path.join(d, day))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kvk', type=int)
    ap.add_argument('roster')
    ap.add_argument('--date', required=True)
    ap.add_argument('--overrides')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    over = {r['name']: r['governor_id'] for r in read(args.overrides)} if args.overrides else {}
    by = all_names()
    day, exp = latest_export()
    near = lambda gid, p: gid in exp and abs(exp[gid][1] - p) <= POWER_TOL * p
    rows, used = [], set()
    for line in open(args.roster, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'):
            continue
        alliance, rank, name, power = line.split('|')
        p = int(power)
        note, how = '', 'name'
        if name in over:
            gid, how = over[name], 'override'
        else:
            hit = sorted(by.get(norm(name), set()))
            m = re.search(r'(\d{6,})$', name)
            if m and not hit:
                hit = [m.group(1)]
            close = [g for g in hit if near(g, p)]
            if len(hit) == 1:
                gid = hit[0]
                if gid in exp and not near(gid, p):
                    note = f'~~ power differs: {name} {p:,} vs export {exp[gid][0]} {exp[gid][1]:,} ({gid})'
            elif len(close) == 1:
                gid, how = close[0], 'name+power'
            else:
                # closest power in the latest export with a similar name
                cand = sorted((abs(v[1] - p), g) for g, v in exp.items() if g not in used and abs(v[1] - p) <= POWER_TOL * p)
                cand = [g for _, g in cand if difflib.SequenceMatcher(None, norm(name).casefold(), norm(exp[g][0]).casefold()).ratio() >= 0.5]
                gid, how = (cand[0], 'power') if cand else ('', '')
                note = (f'~~ by power, please confirm: {name} {p:,} -> {exp[gid][0]} {exp[gid][1]:,} ({gid})' if gid
                        else f'-- not found (name only): {name} {p:,}' + (f' (ambiguous: {hit})' if hit else ''))
        if gid in used:
            note = f'!! {name}: ID {gid} already used by another roster row'
        used.add(gid)
        if note:
            print(note)
        rows.append(dict(alliance=alliance, rank=rank, name=name, power=p, governor_id=gid, match=how))
    print(f'{len(rows)} governors, total power {sum(r["power"] for r in rows):,}; '
          f'{sum(1 for r in rows if r["governor_id"])} matched (export {day})')
    if not args.write:
        print('Rerun with --write to save.')
        return
    out = os.path.join(TRACKER, 'kvk', f'kvk{args.kvk}_roster.csv')
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['alliance', 'rank', 'name', 'power', 'governor_id', 'match'])
        w.writeheader()
        w.writerows(rows)
    meta = os.path.join(TRACKER, 'kvk', 'rosters.csv')
    old = [r for r in read(meta) if r['kvk'] != str(args.kvk)] if os.path.exists(meta) else []
    with open(meta, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['kvk', 'date'])
        w.writeheader()
        w.writerows(sorted(old + [dict(kvk=args.kvk, date=args.date)], key=lambda r: int(r['kvk'])))
    print(f'-> {os.path.relpath(out, os.path.dirname(TRACKER))}')


if __name__ == '__main__':
    main()
