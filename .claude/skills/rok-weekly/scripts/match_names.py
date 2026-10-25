"""Shared by the event importers: match screen names to Governor IDs (accounts, scans, member exports)."""
import csv
import difflib
import os
import re
import unicodedata

TRACKER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'tracker'))


def norm(s):
    """Loose key: NFKC, no spaces, RoK decoration glyphs folded. Case is KEPT (Senopati != SenOpati)."""
    s = unicodedata.normalize('NFKC', s).replace(' ', '')
    for a, b in (('✕', 'x'), ('メ', 'x'), ('乂', 'x'), ('乄', 'x'), ('〆', 'x'), ('·', ''), ('٠', '')):
        s = s.replace(a, b)
    return s


def read(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def known_names():
    """{governor_id: name}: accounts, then the scan, then the member exports, newest last (newest name wins)."""
    names = {r['governor_id']: r['name'] for r in read(os.path.join(TRACKER, 'accounts.csv')) if r['governor_id']}
    for folder in ('scans', 'names'):
        d = os.path.join(TRACKER, folder)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv', f):
                names.update({r['governor_id']: r['name'] for r in read(os.path.join(d, f)) if r['governor_id']})
    return names


def matcher(names, overrides):
    """name -> (governor_id or '', note); note is '' for a sure match."""
    by_key = {}
    for gid, n in names.items():
        by_key.setdefault(norm(n), []).append(gid)

    def match(name):
        if name in overrides:
            return overrides[name], ''
        hit = by_key.get(norm(name), [])
        if len(hit) == 1:
            return hit[0], ''
        if len(hit) > 1:
            return '', f'?? ambiguous: {name} -> {[names[g] for g in hit]} (add to overrides)'
        close = [k for k in difflib.get_close_matches(norm(name), by_key, 3, 0.8) if len(by_key[k]) == 1]
        if close:
            gid = by_key[close[0]][0]
            return gid, f'~~ close match, please confirm: {name} -> {names[gid]} ({gid})'
        return '', f'-- not found (tracked by name only): {name}'
    return match
