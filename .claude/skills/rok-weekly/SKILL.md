---
name: rok-weekly
description: Process a week of Rise of Kingdoms 3514 alliance activity (fort destroyer + tech donation rankings from screenshots or screen recordings), update the offense tracker, and produce the weekly report, in-game mails and public dashboard. Use when the user drops a new "Activity <dates>" folder, says "process this week", marks accounts as farm/R4, records a paid fine, or changes the weekly rules.
---

# RoK 3514 weekly activity

Everything lives under the project root (this repo). The tracker does the maths; your job is
to read the rankings accurately, match names to Governor IDs, and keep `accounts.csv` correct.

## Files

| Path | What it is |
|---|---|
| `tracker/track.py` | Recomputes everything from scratch: offenses, fines, clearance, reports, mails, dashboard. Rules are constants at the top (`MIN_FORTS`, `MIN_TECH`, `REWARDS`, `BANK`, `MAIL_LIMIT`…) |
| `tracker/accounts.csv` | One row per account: `governor_id, name, type (main/farm), role (R4/R5/blank), confirmed, previous_names`. Accounts with no ID are keyed by name |
| `tracker/scans/<date>.csv` | Kingdom scans (from `TOP500-<date>-….xlsx` via `scripts/import_scan.py`). The newest one is the **master player list** on the dashboard's Players tab: every governor with alliance, power, kill points. Events are tracked for `MAIN_ALLIANCE` ([14-X]THE MORTICIANS) only |
| `tracker/weeks/<monday>.csv` | One file per week: `governor_id, name, fort_rank, forts, tech_rank, tech` (blank = not captured) |
| `tracker/fines_paid.csv` | `governor_id, name, week, gold_paid, note`. `week` = the Monday of the week the fine was issued. Hand-entered payments only |
| `tracker/fines_online.csv` | Same columns, payments R4s marked on the dashboard; written by `track.py --pull` (generated) |
| `tracker/accounts_online.csv` | `governor_id, name, type, approved_by, decided`: farm/main changes R4s proposed on the dashboard and the admin approved in the sheet; written by `track.py --pull`, overrides `accounts.csv` (generated) |
| `.github/workflows/recalc.yml` + `tracker/publish_ci.sh` | GitHub Action: `track.py --pull` and republish the dashboard. Started by the sheet on approval, hourly, or `gh workflow run recalc.yml`. Uses the `DASHBOARD_DEPLOY_KEY` secret; refuses to publish if the live dashboard has a week the repo lacks |
| `tracker/fines_ledger/` | Apps Script (clasp project, owned by the Google account clasp is logged in as) bound to the "3514 Fines" Google Sheet: `Officers` tab = one personal dashboard key per R4, `Payments` tab = append-only payment log, `Accounts` tab = farm/main proposals (status proposed/approved/rejected; the admin, i.e. the user / sheet owner, not the R5, decides via the **3514** menu; approvers (`APPROVERS` in `Code.js` or `approver = yes` in Officers, e.g. Totos メtreme, ＡＧＡＭ) can approve/reject on the dashboard Review tab, and their own farm/main changes (single or multi-select in the master list) apply at once, which starts the Action using a GitHub token kept in Script Properties). `track.py` `FINES_URL` points at its web app |
| `tracker/reports/<monday>.md` | Weekly report (generated) |
| `tracker/mails/<monday>/` | In-game alliance mails, RoK rich text, each ≤ 2000 chars (generated) |
| `tracker/status.csv`, `tracker/offense_log.csv` | Current status and full offense history (generated) |
| `tracker/dashboard_template.html` → `tracker/dashboard/index.html` | Public dashboard (generated; `dashboard/` is its own git repo) |
| `tracker/publish.sh` | Rebuilds and pushes the dashboard to GitHub Pages |
| `Activity <d-d mon yyyy>/` | Raw screenshots / videos / member export the user provides each week |

Never hand-edit generated files; change inputs and rerun `python3 tracker/track.py`.

## Rules (current)

- Minimum per week: **70 forts** and **50,000 tech**. Tech has no penalty — it is reported only.
- Fort penalties apply to **main accounts, including R4 and R5**; farms never get penalties.
  1st forgiven + Low Contribution label · 2nd 500K gold × missing forts · 3rd 1M gold × missing + unpaid fines · 4th must migrate (or zeroed).
- **2 passing weeks in a row wipe all current offenses**; history stays in `offense_log.csv`; unpaid fines stay owed.
- Rewards: top 10 by forts among main accounts **including R4**; **farms and the R5 excluded**. 1 Legendary Trophy + 10K VIP (+$5 Flux if ≥200 forts), 2 Epic Trophy + 5K VIP, 3 Epic Trophy, 4–8 Elite Trophy, 9–10 Advanced Trophy; every R4 also gets an Advanced Trophy (on top of any top-10 reward).
- Fines are paid to the bank KD account **KINGDOM 3514** (the R5).
- Fort counts are per-participant credits (every rally member gets credit). A sum of forts is **"fort credits"**, never "forts destroyed".

## Farm rule

Only accounts **listed as farm** in `accounts.csv` (or approved as farm on the dashboard) are farms. Every other
account, including names with "farm" or an `F<number>` suffix, defaults to **main with `confirmed = no`**; a
farm-looking name is only a hint (dashboard Review tab). List new unconfirmed mains that failed the minimum,
flag the farm-looking ones, and ask the user.
When the user says an account is a farm (or R4), set `type`/`role` and `confirmed = yes` in `accounts.csv` and rerun.
R4s can also propose farm/main on the dashboard; once the admin (the user) approves, `accounts_online.csv` overrides `accounts.csv`.
To make such a change permanent, copy it into `accounts.csv`.
For a new or removed R4, also update the `R4` list in `tracker/fines_ledger/Code.js`, then from that folder
`clasp push -f && clasp update-deployment <deployment id from FINES_URL>`, and have the user click
**3514 → Create keys for missing R4s** in the sheet (adds a key + link for new names; to remove an R4, set their
`status` to `revoked` in the Officers tab). **3514 → New key for selected R4** rotates one R4's key.
Changing an account's type applies retroactively to every week.

## New kingdom scan

When the user drops a new `TOP500-<date>-….xlsx`: `.venv/bin/python .claude/skills/rok-weekly/scripts/import_scan.py FILE`,
rerun `track.py`, push, publish. The master list, alliances and farm hints update from it.

## New member export (latest names)

`data-from-ingame/3514_<from>_<to>_statsExport.xlsx` is the in-game member export for the whole kingdom.
`.venv/bin/python .claude/skills/rok-weekly/scripts/import_export.py FILE` (check renames) then `--write`:
writes `tracker/names/<to-date>.csv` (latest name + power per ID, wins over scan and week names on the dashboard)
and records renames in `accounts.csv`. Governors below the TOP500 scan join the master list without an alliance.
Its kill points / kills cover only its date range, so they are not used as lifetime stats.
Older exports can be imported too: they only add name history (the pop-up's Name history is built from every
dated week file, scan and export; the most recently seen name is the current one) and never rename accounts.
Old name lists (e.g. a past KvK sheet shared by link) seed history the same way:
`python3 .claude/skills/rok-weekly/scripts/import_name_list.py <sheet link or csv> --date YYYY-MM-DD`
(use the date the names were current, e.g. the end of the period the sheet covers; matched by Governor ID).

## Past KvK sheets

`python3 .claude/skills/rok-weekly/scripts/import_kvk.py N <sheet link> --date YYYY-MM-DD [--estimated]` imports
one KvK (layout recognised from its headers: KP / DKP / Acclaim, targets, fines, status; several scans -> first and
last) into `tracker/kvk/kvk<N>.csv` + `kvks.csv`, and its names into `tracker/names/<date>_kvk<N>.csv` (Name
history, labelled "KvK N"). Shown in the player pop-up and the KvK history tab, matched by Governor ID.
Imported: KvK 3-10. Dates of KvK 3, 5, 7, 8, 9 are estimated (≈ Jan 2025, Jul 2025, Nov 2025, Feb 2026, May 2026) until
the user gives them; rerun with the real `--date` to fix.

## Dashboard tabs

Players (master list + player view) · Weekly activity · Fines · KvK history · Review (R4 mode only: proposals waiting for the admin,
and unconfirmed accounts in the alliance with farm hints from `farm_hints()` in `track.py`). Links: `#t=<tab>`, `#t=players&p=<name>`.
Future events (KvK, MGE, AoO, 20 GH…) get their own tab and data folder, sharing the master list, R4 keys and fines ledger.

## Processing a week

0. Python helpers need the project venv: `.venv/bin/python` (Pillow + openpyxl). If `.venv` is missing:
   `python3 -m venv .venv && .venv/bin/pip install pillow openpyxl`.
1. **Find the inputs** in the new `Activity …` folder: fort ranking, tech ranking (skip "Resource Assistance"),
   and usually a member export `*_statsExport.xlsx` (Character ID, Username, Power…). The week's Monday is the file name.
2. **Screen recordings**: for each video run
   `.venv/bin/python .claude/skills/rok-weekly/scripts/extract_frames.py VIDEO <scratch>/fort` (or `/tech`).
   Read every `start_*.png` first — **rank 1 is only visible in the first fraction of a second**.
   Then read `stack_*.png` in order. Screenshots: read them directly.
   Tell rankings apart by the title (Fort Destroyer / "Peringkat Penghancur Benteng" vs Mad Scientist).
3. **Transcribe** into two pipe files in scratch: `rank|name|forts` and `rank|name|tech`. Copy names exactly,
   including decorations (ᴴᴹ, メ, 么, superscripts). Case matters: `Senopati ᵀᴹ` and `SenOpati ᵀᴹ` are different players.
4. **Check and match**:
   `.venv/bin/python .claude/skills/rok-weekly/scripts/build_week.py MONDAY fort.txt tech.txt EXPORT.xlsx`
   - `!!` lines are blocking (missing ranks, out-of-order values, name sets differ) — re-read those frames.
   - `~~` close matches: verify each one by hand against the export (a wrong match moves offenses to the wrong
     player — e.g. `KNTLkecil F4` once fuzzy-matched `KNTLkecil F3`). Put corrections in an overrides CSV
     (`name,governor_id`, empty ID = name-only) and rerun with `--overrides`.
   - When clean, rerun with `--write`. It writes the week file, records renames and adds new accounts.
5. **Run** `python3 tracker/track.py`, then read `tracker/reports/<monday>.md`.
6. **Report to the user**: renames (especially R4/R5), who left, rewards, 2nd+ offenses with fines, new 1st offenses,
   tech below minimum, notable movers, and the list of unconfirmed mains to classify. Point to the mails folder.
7. **Push** the repo changes (the recalc Action builds from GitHub, and won't publish over a newer live dashboard),
   then **publish** the dashboard: `sh tracker/publish.sh` (ask first if unsure; it pushes to a public GitHub Pages site).

## Other requests

- **Fine paid**: R4s mark payments on the dashboard with their personal `?key=` link; `publish.sh` pulls them.
  Only if the user reports one directly, append to `tracker/fines_paid.csv` (week = Monday the fine was issued) and rerun.
- **Rule change**: edit the constants in `tracker/track.py`; the rules mail (`5_fort_rules.txt`) regenerates from them.
- **Missing rank or wrong number** reported by the user: fix the week CSV row, rerun.

## Gotchas

- WhatsApp recordings are 848×392; the default crop in `extract_frames.py` fits that layout. Other devices may need `--crop`.
- Ask for the original video or "send as document" — WhatsApp video compression can blur superscript tags.
- A week where only part of the ranking was captured is marked partial on the dashboard automatically
  (fewer than 90% of the usual player count). Players outside the captured ranks get no offense that week.
- `tracker/dashboard/` is a separate git repo (public). Commits there use the GitHub noreply address, never the work email.
