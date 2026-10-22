#!/usr/bin/env python3
"""3514 weekly fort/tech tracker.

Reads:
  accounts.csv      governor_id, name, type (main/farm), confirmed
  weeks/<monday>.csv governor_id, name, fort_rank, forts, tech_rank, tech  (blank = not captured)
  fines_paid.csv    governor_id, name, week, gold_paid, note  (entered by hand)
  fines_online.csv  same columns, pulled from the R4 fines ledger (Google Sheet) by --pull
  scans/<date>.csv  latest kingdom scan = master player list (made by import_scan.py from the TOP500 xlsx)
  names/<date>.csv  governor_id, name, power from the latest member export (import_export.py): current name
                    per ID, plus governors below the TOP500 scan
  accounts_online.csv  governor_id, name, type, approved_by, decided: farm/main changes R4s proposed and the
                    admin approved in the ledger (--pull); they override accounts.csv

Writes:
  status.csv                 current offense status per account
  reports/<monday>.md        weekly report for each week file

Usage: python3 track.py          rebuild from local files
       python3 track.py --pull   first refresh fines_online.csv and accounts_online.csv from the ledger
"""
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import date, timedelta

MIN_FORTS = 70
MIN_TECH = 50_000
FLUX_FORTS = 200
MAIL_LIMIT = 2000  # in-game mail character limit
BANK = 'KINGDOM 3514'  # bank KD account that receives fines
CLEAR_AFTER = 2  # consecutive passing weeks that clear all recorded offenses

# R4 fines ledger (Apps Script web app in fines_ledger/); the dashboard reads and writes it.
FINES_URL = 'https://script.google.com/macros/s/AKfycbxjPVSNgqPqh5ki0M_dEydbNi2kFoV2O6xjH8qS84i9BrJhKKW3FfEwBC82XMDeGVz6/exec'

HERE = os.path.dirname(os.path.abspath(__file__))

# Farm-looking names ("Farm" anywhere, or an F<number> suffix). Only a hint: accounts not listed as farm
# in accounts.csv (or approved as farm on the dashboard) are treated as main.
FARM_NAME = re.compile(r'farm|\bF\d+\s*$', re.I)
# Farm-looking name endings stripped to find the main a farm belongs to ("NAHKODA F1", "EdėlwėiS 02", "Totos Farm").
FARM_TAIL = re.compile(r'(\s*(farm\w*|f\s*\d+|f|\d+))+\s*$', re.I)
# Events are tracked for this alliance only; the master list shows every governor in the scan.
MAIN_ALLIANCE = '[14-X]THE MORTICIANS'

# Top-10 fort rewards; farms and the R5 are not eligible, R4s are. Every R4 also gets R4_REWARD.
REWARDS = ['Legendary Trophy + 10K VIP', 'Epic Trophy + 5K VIP', 'Epic Trophy'] + \
          ['Elite Trophy'] * 5 + ['Advanced Trophy'] * 2
R4_REWARD = 'Advanced Trophy'

NEXT = {1: 'Forgiven + Low Contribution label',
        2: '500K gold per missing fort',
        3: '1M gold per missing fort + unpaid fines',
        4: 'Must migrate (or zeroed)'}


def read(path):
    p = os.path.join(HERE, path)
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def key(r):
    return r['governor_id'] or 'name:' + r['name']


def num(v):
    return int(v.replace(',', '')) if v and v.strip() else None


def gold(n):
    if n >= 1_000_000_000:
        return f'{n / 1e9:g}B gold'
    if n >= 1_000_000:
        return f'{n / 1e6:g}M gold'
    return f'{n / 1e3:g}K gold'


def fine_id(k, wk):
    """Stable public id for one week's fine, so the dashboard never needs Governor IDs."""
    return hashlib.sha1(f'3514|{k}|{wk}'.encode()).hexdigest()[:10]


def account_id(k):
    """Stable public id for one account (same idea as fine_id)."""
    return hashlib.sha1(f'3514|acct|{k}'.encode()).hexdigest()[:10]


def pull_ledger():
    """Ledger -> fines_online.csv (payments, matched to offense_log.csv) and accounts_online.csv
    (approved farm/main changes, matched to every known account)."""
    for attempt in (1, 2):  # the web app can take a while to wake up, especially right after a redeploy
        try:
            with urllib.request.urlopen(FINES_URL, timeout=60) as resp:
                ledger = json.load(resp)
            break
        except OSError:
            if attempt == 2:
                raise
            print('Ledger slow to answer, retrying once')
    pull_accounts(ledger.get('accounts', {}))
    paid = ledger['paid']
    fines = {fine_id(r['governor_id'], r['week']): r for r in read('offense_log.csv') if num(r['fine_gold'])}
    with open(os.path.join(HERE, 'fines_online.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'week', 'gold_paid', 'note'])
        for fid, p in sorted(paid.items(), key=lambda kv: kv[1]['time']):
            if fid in fines:
                r = fines[fid]
                w.writerow([r['governor_id'], r['name'], r['week'], int(p['amount']),
                            f"marked by {p['by']} {p['time'][:10]}"])
            else:
                print(f'Ledger payment {fid} matches no fine in offense_log.csv, skipped')
    print(f'Pulled {len(paid)} payment(s) from the fines ledger')


def pull_accounts(changes):
    names = {key(a): a['name'] for a in read('accounts.csv')}
    for wk in os.listdir(os.path.join(HERE, 'weeks')):
        if wk.endswith('.csv'):
            names.update({key(r): r['name'] for r in read(f'weeks/{wk}')})
    ids = {account_id(k): k for k in names}
    approved = {i: c for i, c in changes.items() if c.get('type') in ('farm', 'main')}
    with open(os.path.join(HERE, 'accounts_online.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'type', 'approved_by', 'decided'])
        for i, c in sorted(approved.items(), key=lambda kv: kv[1]['decided']):
            if i not in ids:
                print(f'Ledger account change {i} matches no known account, skipped')
                continue
            k = ids[i]
            gid = '' if k.startswith('name:') else k
            w.writerow([gid, names[k], c['type'], f"proposed by {c['by']}", c['decided'][:10]])
    print(f'Pulled {len(approved)} approved account change(s) from the ledger')


def penalty(offense, missing, unpaid):
    """Return (fine_in_gold, action text) for the Nth offense."""
    if offense == 1:
        return 0, 'Forgiven + Low Contribution label'
    if offense == 2:
        fine = 500_000 * missing
        return fine, f'Fine 500K x {missing} = {gold(fine)}'
    if offense == 3:
        fine = 1_000_000 * missing
        extra = f' + unpaid {gold(unpaid)}' if unpaid else ''
        return fine, f'Fine 1M x {missing} = {gold(fine)}{extra}'
    return 0, 'MUST MIGRATE (or account zeroed)'


def main():
    accounts = {key(a): a for a in read('accounts.csv')}
    for o in read('accounts_online.csv'):  # admin-approved farm/main changes from the dashboard win
        a = accounts.setdefault(key(o), dict(governor_id=o['governor_id'], name=o['name'], type='', role='',
                                             confirmed='', previous_names=''))
        a.update(type=o['type'], confirmed='yes')
    paid, by_hand = {}, {}
    for src in ('fines_paid.csv', 'fines_online.csv'):
        for p in read(src):
            k = (key(p), p['week'])
            paid[k] = paid.get(k, 0) + (num(p['gold_paid']) or 0)
            if src == 'fines_paid.csv':
                by_hand[k] = paid[k]

    weeks = sorted(f[:-4] for f in os.listdir(os.path.join(HERE, 'weeks')) if f.endswith('.csv'))
    state = {}  # key -> current offense status
    log = []  # every offense and clearance, kept even after a record is wiped
    history = []  # (week, report lines) for the dashboard
    fines = []  # every fine, for the dashboard's fines panel

    for wk in weeks:
        rows = read(f'weeks/{wk}.csv')
        lines = []
        for r in rows:
            k = key(r)
            acc = accounts.get(k, {})
            typ = acc.get('type') or 'main'
            forts, tech = num(r['forts']), num(r['tech'])
            s = state.setdefault(k, dict(offenses=0, streak=0, unpaid=0, lifetime=0, cleared=0, last=''))
            s.update(name=r['name'], type=typ, role=acc.get('role', ''))
            row = dict(key=k, name=r['name'], type=typ, role=acc.get('role', ''), forts=forts, tech=tech,
                       offense='', action='', due=0,
                       miss_f=max(0, MIN_FORTS - forts) if forts is not None else None,
                       miss_t=max(0, MIN_TECH - tech) if tech is not None else None)
            if typ == 'main' and forts is not None:
                if forts >= MIN_FORTS:
                    s['streak'] += 1
                    if s['offenses'] and s['streak'] >= CLEAR_AFTER:
                        row['action'] = f'Cleared ({CLEAR_AFTER} weeks in a row)'
                        log.append([wk, k, s['name'], s['role'], forts, 0, 'cleared',
                                    f"{s['offenses']} offense(s) wiped", 0, s['unpaid']])
                        s['offenses'] = 0
                        s['cleared'] += 1
                else:
                    s['streak'] = 0
                    s['offenses'] += 1
                    s['lifetime'] += 1
                    s['last'] = wk
                    fine, act = penalty(s['offenses'], row['miss_f'], s['unpaid'])
                    s['unpaid'] += fine
                    row.update(offense=s['offenses'], action=act, due=s['unpaid'])
                    log.append([wk, k, s['name'], s['role'], forts, row['miss_f'],
                                f"offense {s['offenses']}", act, fine, s['unpaid']])
                    if fine:
                        fines.append(dict(id=fine_id(k, wk), k=k, n=s['name'], wk=wk, a=fine, m=row['miss_f'],
                                          h=by_hand.get((k, wk), 0)))
            s['unpaid'] = max(0, s['unpaid'] - paid.get((k, wk), 0))
            lines.append(row)
        seen = {key(r) for r in rows}
        for k, a in accounts.items():  # R4s missing from this week's screenshots still get listed
            if a.get('role') == 'R4' and k not in seen:
                lines.append(dict(name=a['name'], type=a['type'], role='R4', forts=None, tech=None,
                                  offense='', action='', due=0, miss_f=None, miss_t=None))
        write_report(wk, lines)
        history.append((wk, lines))

    with open(os.path.join(HERE, 'status.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['governor_id', 'name', 'type', 'role', 'offenses', 'passing_streak', 'unpaid_gold',
                    'next_if_fail', 'lifetime_offenses', 'times_cleared', 'last_offense_week'])
        for k, s in sorted(state.items(), key=lambda kv: (-kv[1]['offenses'], -kv[1]['lifetime'], kv[1]['name'])):
            nxt = NEXT.get(s['offenses'] + 1, NEXT[4]) if s['type'] == 'main' else '-'
            w.writerow([k, s['name'], s['type'], s['role'], s['offenses'], s['streak'], s['unpaid'], nxt,
                        s['lifetime'], s['cleared'], s['last']])

    with open(os.path.join(HERE, 'offense_log.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['week', 'governor_id', 'name', 'role', 'forts', 'missing_forts', 'event', 'penalty',
                    'fine_gold', 'total_owed_gold'])
        w.writerows(log)

    write_dashboard(history, state, accounts, fines)


def write_report(wk, lines):
    start = date.fromisoformat(wk)
    end = start + timedelta(days=6)
    title = f'{start.day} {start:%b} – {end.day} {end:%b %Y}'
    main_fail = sorted([l for l in lines if l['offense']], key=lambda l: (-l['offense'], -(l['miss_f'] or 0)))
    farm_low = [l for l in lines if l['type'] == 'farm' and l['miss_f']]
    tech_low = sorted([l for l in lines if l['miss_t'] and l['type'] == 'main'], key=lambda l: -l['miss_t'])
    cleared = [l for l in lines if l['action'].startswith('Cleared')]
    ranked = sorted([l for l in lines if l['forts'] is not None and l['type'] == 'main' and l['role'] != 'R5'],
                    key=lambda l: -l['forts'])
    r4 = [l for l in lines if l['role'] == 'R4']

    out = [f'# Weekly Activity Report – {title}', '',
           f'Rules: min **{MIN_FORTS} forts** and **{MIN_TECH:,} tech** per week. '
           'Penalties apply to main accounts only; farms are listed at the end with no penalty.', '',
           '## Summary', '', '| | Players |', '|---|---|',
           f'| Main accounts below fort minimum | {len(main_fail)} |',
           f'| Main accounts below tech minimum | {len(tech_low)} |',
           f'| Farms below fort minimum (no penalty) | {len(farm_low)} |',
           f'| Offenses cleared this week | {len(cleared)} |', '',
           '## Ranking rewards', '', 'Farms and the R5 are excluded from the top 10; R4s can place.', '',
           '| Place | Player | Forts | Reward |', '|---|---|---|---|']
    for i, l in enumerate(ranked[:len(REWARDS)]):
        reward = REWARDS[i]
        if i == 0:
            reward += ' + $5 Flux' if l['forts'] >= FLUX_FORTS else f' (no Flux: under {FLUX_FORTS})'
        out.append(f"| {i + 1} | {l['name']} | {l['forts']} | {reward} |")
    out += ['', f'R4 ({R4_REWARD}):', '']
    out += [f"- {l['name']}" + (f" ({l['forts']} forts)" if l['forts'] is not None else ' (forts not captured)')
            for l in r4]
    out += ['', '## Fort penalties (main accounts)', '',
           '| Player | Forts | Missing | Offense # | Penalty | Total owed |', '|---|---|---|---|---|---|']
    for l in main_fail:
        out.append(f"| {l['name']} | {l['forts']} | {l['miss_f']} | {l['offense']} | {l['action']} | "
                   f"{gold(l['due']) if l['due'] else '-'} |")
    if cleared:
        out += ['', '## Cleared this week', ''] + [f"- {l['name']}" for l in cleared]
    out += ['', '## Tech donation below minimum (main accounts)', '', '| Player | Tech | Missing |', '|---|---|---|']
    out += [f"| {l['name']} | {l['tech']:,} | {l['miss_t']:,} |" for l in tech_low]
    out += ['', '## Farms below fort minimum (no penalty)', '', '| Player | Forts | Missing |', '|---|---|---|']
    out += [f"| {l['name']} | {l['forts']} | {l['miss_f']} |" for l in farm_low]
    out.append('')
    with open(os.path.join(HERE, 'reports', f'{wk}.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    write_mails(wk, title, lines, ranked, r4, main_fail, tech_low)


def write_mails(wk, title, lines, ranked, r4, main_fail, tech_low):
    """In-game alliance mails (RoK rich text), one file per topic, in mails/<monday>/."""
    head = lambda t: [f'<size=30><b>3514 | {t}</b></size>', f'<b>{title}</b>', '',
                      '<size=24><color=navy>══════ ✿ ══════</color></size>', '']
    foot = ['', '<b>Contribute and keep Kingdom 3514 strong!</b>']
    first = [l for l in main_fail if l['offense'] == 1]
    fined = [l for l in main_fail if l['offense'] >= 2]
    mains = [l for l in lines if l['type'] == 'main' and l['forts'] is not None]
    forts_all = sum(l['forts'] or 0 for l in lines)
    tech_all = sum(l['tech'] or 0 for l in lines)

    counted = [l for l in lines if l['forts'] is not None]
    forts_main = sum(l['forts'] for l in mains)
    tech_main = sum(l['tech'] or 0 for l in mains)
    summary = head('WEEKLY SUMMARY') + [
        f'Fort Credits: <b>{forts_all:,}</b> (main accounts: {forts_main:,})',
        '<i>Sum of every member\'s fort count. A fort destroyed in a rally counts once for each '
        'participant, so this is not the number of unique forts destroyed.</i>',
        f'Total Tech Donations: <b>{tech_all:,}</b> (main accounts: {tech_main:,})',
        f'<i>Sum of all {len(counted)} members in the ranking, farms included.</i>', '',
        f'Main accounts reaching {MIN_FORTS} Forts: <b>{len(mains) - len(main_fail)}/{len(mains)}</b>',
        f'Main accounts reaching {MIN_TECH // 1000}K Tech: <b>{len(mains) - len(tech_low)}/{len(mains)}</b>', '',
        '<b><color=navy>TOP FORT REWARDS</color></b>']
    colors = ['#DAA520', '#808080', '#CD7F32']
    for i, l in enumerate(ranked[:len(REWARDS)]):
        reward = REWARDS[i] + (' + $5 Flux' if i == 0 and l['forts'] >= FLUX_FORTS else '')
        place = f'<color={colors[i]}><b>{i + 1}.</b></color>' if i < 3 else f'<b>{i + 1}.</b>'
        summary.append(f"{place} {l['name']} ({l['forts']}) – {reward}")
    summary += ['', f'<b>R4 – {R4_REWARD}</b>'] + [f"• {l['name']}" for l in r4] + [
        '', '<b><color=red>LOW CONTRIBUTION</color></b>',
        f'1st offense (forgiven): <b>{len(first)}</b> players',
        f'Fined: <b>{len(fined)}</b> players',
        f'Below {MIN_TECH // 1000}K Tech: <b>{len(tech_low)}</b> players',
        '', 'Check the following mails for the full lists.'] + foot

    ordinal = {2: '2nd', 3: '3rd'}
    m1 = ('2_fort_1st_offense', 'FORT – 1st OFFENSE', [
        f'These main accounts did not reach <b>{MIN_FORTS} Forts</b> this week.',
        'This is your <b>1st offense</b>: forgiven, with a <color=red><b>Low Contribution</b></color> label.',
        f'<i>Name – Forts/{MIN_FORTS}</i>', ''],
        [f"• {l['name']} – {l['forts']}/{MIN_FORTS}" for l in first],
        ['', '<b>Next failure: 500K gold x missing Forts.</b>',
         f'Reach {MIN_FORTS} Forts for {CLEAR_AFTER} weeks in a row to clear your record.'])

    fines = []
    for l in fined:
        what = '<color=red><b>MUST MIGRATE</b></color>' if l['offense'] >= 4 else \
            f"<b>{gold(l['due']).replace(' gold', '')}</b> ({ordinal[l['offense']]})"
        fines.append(f"• {l['name']} – {l['forts']}/{MIN_FORTS} – {what}")
    m2 = ('3_fort_fines', 'FORT – FINES', [
        f'These main accounts missed <b>{MIN_FORTS} Forts</b> again. Pay your fine this week.',
        f'<i>Name – Forts/{MIN_FORTS} – fine in gold (offense)</i>', ''],
        fines,
        ['', f'<b>Send your fine to the bank KD: <color=#DAA520>{BANK}</color></b>', '',
         '<b>PAY PER MISSING FORT</b>',
         '2nd: 500K gold = 1M Food / 1M Wood / 750K Stone',
         '3rd: 1M gold = 2M Food / 2M Wood / 1.5M Stone', '',
         '<color=red><b>Next failure: 1M gold x missing Forts + unpaid fines.</b></color>',
         f'Reach {MIN_FORTS} Forts for {CLEAR_AFTER} weeks in a row to clear your record.'])

    m3 = ('4_low_tech', 'LOW TECH DONATION', [
        f'These main accounts donated less than <b>{MIN_TECH:,}</b> tech points this week.', ''],
        [f"• {l['name']} – {l['tech']:,}" for l in sorted(tech_low, key=lambda l: l['tech'])],
        ['', f'Please reach <b>{MIN_TECH // 1000}K</b> next week.'])

    rules = ['<size=30><b>3514 | WEEKLY FORT RULES</b></size>', '',
             '<size=24><color=navy>══════ ✿ ══════</color></size>', '',
             '<b><color=navy>WEEKLY REQUIREMENTS</color></b>',
             f'[ FORT ] Minimum <b>{MIN_FORTS} Forts/week</b>',
             f'[ TECH ] Minimum <b>{MIN_TECH // 1000}K Tech Donations/week</b>', '',
             '<b>RANKING REWARDS</b> <i>(main accounts incl. R4; farms and R5 excluded)</i>',
             f'<color=#DAA520><b>1st:</b></color> {REWARDS[0]} + $5 Flux <i>(min {FLUX_FORTS} Forts)</i>',
             f'<color=#808080><b>2nd:</b></color> {REWARDS[1]}',
             f'<color=#CD7F32><b>3rd:</b></color> {REWARDS[2]}',
             f'<b>4th–8th:</b> {REWARDS[3]}',
             f'<b>9th–10th:</b> {REWARDS[8]}',
             f'<b>R4:</b> {R4_REWARD}', '',
             '<b><color=red>MAIN ACCOUNT FORT RULES</color></b>',
             'Applies to <b>all main accounts</b>, including R4 and R5. Farms have no penalty.',
             '•  <b>1st offense:</b> Forgiven + Low Contribution label',
             '•  <b>2nd:</b> 500K gold x missing Forts',
             '•  <b>3rd:</b> 1M gold x missing Forts + unpaid previous fines',
             '•  <b>4th:</b> Must migrate. Failure to migrate means your account will be '
             '<color=red><b>ZEROED</b></color>.', '',
             '<b>FINE PAYMENT</b>',
             f'Send to the bank KD: <b>{BANK}</b>',
             'Per missing Fort:',
             '•  500K gold = 1M Food / 1M Wood / 750K Stone',
             '•  1M gold = 2M Food / 2M Wood / 1.5M Stone', '',
             '<b>PENALTY CLEARANCE</b>',
             f'Reach the Fort minimum for <b>{CLEAR_AFTER} weeks in a row</b> to clear all recorded offenses.'
             ] + foot

    d = os.path.join(HERE, 'mails', wk)
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):
        os.remove(os.path.join(d, old))
    for name, body in [('1_summary', summary), ('5_fort_rules', rules)]:
        with open(os.path.join(d, f'{name}.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(body) + '\n')
    for name, t, intro, items, outro in (m1, m2, m3):
        parts = split_mail(t, head, intro, items or ['(none)'], outro + foot)
        for i, body in enumerate(parts):
            suffix = f'_part{i + 1}' if len(parts) > 1 else ''
            with open(os.path.join(d, f'{name}{suffix}.txt'), 'w', encoding='utf-8') as f:
                f.write(body)
    for name in os.listdir(d):
        assert len(open(os.path.join(d, name), encoding='utf-8').read()) <= MAIL_LIMIT, name


def split_mail(title, head, intro, items, outro):
    """Pack list items into as few mails as possible, each at most MAIL_LIMIT characters.
    Intro goes in the first part, outro in the last; parts get (1/2), (2/2)… in the title."""
    def build(chunks):
        n = len(chunks)
        return ['\n'.join(head(title + (f' ({i + 1}/{n})' if n > 1 else '')) + (intro if i == 0 else [])
                          + c + (outro if i == n - 1 else [])) + '\n' for i, c in enumerate(chunks)]
    chunks = [[]]
    for item in items:
        trial = chunks[:-1] + [chunks[-1] + [item]]
        # worst case for size checks: every part carries intro, outro and a (n/n) suffix
        if chunks[-1] and len('\n'.join(head(title + ' (9/9)') + intro + trial[-1] + outro)) >= MAIL_LIMIT:
            chunks.append([item])
        else:
            chunks = trial
    return build(chunks)

def latest(folder):
    """(date, {key: row}) of the newest <folder>/<date>.csv, or ('', {})."""
    d = os.path.join(HERE, folder)
    days = sorted(f[:-4] for f in os.listdir(d) if f.endswith('.csv')) if os.path.isdir(d) else []
    if not days:
        return '', {}
    return days[-1], {key(r): r for r in read(f'{folder}/{days[-1]}.csv')}


def name_history(history):
    """{key: {name: [first_date, last_date]}} from every dated source: week files, scans, member exports."""
    seen = {}
    def add(k, name, day):
        span = seen.setdefault(k, {}).setdefault(name, [day, day])
        span[0], span[1] = min(span[0], day), max(span[1], day)
    for wk, lines in history:
        for l in lines:
            if l.get('key'):
                add(l['key'], l['name'], wk)
    for folder in ('scans', 'names'):
        d = os.path.join(HERE, folder)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith('.csv'):
                for r in read(f'{folder}/{f}'):
                    add(key(r), r['name'], f[:-4])
    return seen


def core(name):
    """Name folded for comparing accounts: NFKC, case-folded, letters and digits only."""
    return ''.join(c for c in unicodedata.normalize('NFKC', name).casefold() if c.isalnum())


def farm_hints(p, mains):
    """Why an unconfirmed account might be a farm (shown to R4s; they decide)."""
    hints = []
    if FARM_NAME.search(p['n']):
        hints.append('Name looks like a farm')
    base = core(FARM_TAIL.sub('', p['n']))
    if len(base) >= 4 and base != core(p['n']):
        owner = next((m for m in mains if m != p['n'] and core(m).startswith(base)), None)
        if owner:
            hints.append(f'Name matches {owner}')
    if 'farm' in p.get('a', '').casefold():
        hints.append(f"In a farm alliance ({p['a']})")
    if p.get('pw') and p.get('kp') is not None and p['kp'] < p['pw']:
        hints.append('Low kill points for its power')
    return hints


def write_dashboard(history, state, accounts, fines):
    """Fill dashboard_template.html with this season's data -> dashboard/index.html (public page).
    Players = everyone in the weekly rankings plus everyone in the latest scan. No Governor IDs go out."""
    ids, players = {}, []
    for wk, lines in history:
        for l in lines:
            if l.get('key') is None or l['forts'] is None:
                continue
            if l['key'] not in ids:
                ids[l['key']] = len(players)
                players.append(dict(n=l['name'], w={}))
            p = players[ids[l['key']]]
            p.update(n=l['name'], t=l['type'], r=l['role'])
            p['w'][wk] = dict(f=l['forts'], x=l['tech'], o=l['offense'] or 0, d=l['due'] or 0)
    scan_day, scan = latest('scans')
    names_day, names = latest('names')
    for k, r in list(scan.items()) + [(k, r) for k, r in names.items() if k not in scan]:
        if k not in ids:  # governors not in the alliance rankings (yet); export-only ones are below the scan
            a = accounts.get(k, {})
            ids[k] = len(players)
            players.append(dict(n=r['name'], t=a.get('type') or 'main',
                                r=a.get('role', ''), w={}))
    for k, i in ids.items():
        s, a, r = state.get(k, {}), accounts.get(k, {}), scan.get(k)
        p = players[i]
        p.update(id=account_id(k), o=s.get('offenses', 0), u=s.get('unpaid', 0), lt=s.get('lifetime', 0),
                 pn=[n for n in a.get('previous_names', '').split(';') if n],
                 c=a.get('confirmed') == 'yes' or bool(p.get('r')))  # c = type confirmed (accounts.csv, admin approval, or R4/R5)
        if r:  # a = alliance, pw = power, kp = kill points, dd = deads, rg = resources gathered (latest scan)
            p.update(a=r['alliance'] if r['alliance'] != '-' else '', pw=num(r['power']), kp=num(r['killpoints']),
                     dd=num(r['deads']), rg=num(r['rss_gathered']))
        new = names.get(k)
        if new:  # the member export is the newest source for names (and power, when newer than the scan)
            for old in (p['n'], r and r['name']):
                if old and old != new['name'] and old not in p['pn']:
                    p['pn'].append(old)
            p['n'] = new['name']
            if names_day >= scan_day or p.get('pw') is None:
                p['pw'] = num(new['power'])
    # hn = name history, oldest first: [name, first seen, last seen] ('' = date unknown, from accounts.csv)
    seen = name_history(history)
    for k, i in ids.items():
        p, spans = players[i], seen.get(k, {})
        if spans:  # current name = the one seen most recently in any source
            newest = max(spans, key=lambda n: (spans[n][1], n == p['n']))
            if newest != p['n']:
                p['pn'] = [n for n in p['pn'] if n != newest] + ([p['n']] if p['n'] not in p['pn'] else [])
                p['n'] = newest
        old = [[n, '', ''] for n in p['pn'] if n not in spans]  # undated: older than anything tracked
        old += sorted(([n, a, b] for n, (a, b) in spans.items() if n != p['n']), key=lambda h: (h[1], h[2]))
        if old:
            cur = spans.get(p['n'], ['', ''])
            p['hn'] = old + [[p['n'], cur[0], cur[1]]]
    mains = [p['n'] for p in players if p['t'] == 'main' and p['c']] + [p['n'] for p in players if p['t'] == 'main' and not p['c']]
    for p in players:
        if not p['c']:
            p['h'] = farm_hints(p, mains)
    # p = player index; Governor IDs stay local. h = paid by hand (fines_paid.csv), not in the ledger.
    fines = [dict({x: v for x, v in f.items() if x != 'k'}, p=ids.get(f['k'])) for f in fines]
    data = dict(weeks=[wk for wk, _ in history], minF=MIN_FORTS, minT=MIN_TECH, players=players,
                fines=fines, finesUrl=FINES_URL, scanDay=scan_day, namesDay=names_day, mainAlly=MAIN_ALLIANCE,
                updated=date.today().isoformat())
    with open(os.path.join(HERE, 'dashboard_template.html'), encoding='utf-8') as f:
        html = f.read()
    os.makedirs(os.path.join(HERE, 'dashboard'), exist_ok=True)
    with open(os.path.join(HERE, 'dashboard', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html.replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False, separators=(',', ':'))))


if __name__ == '__main__':
    if '--pull' in sys.argv:
        pull_ledger()
    main()
