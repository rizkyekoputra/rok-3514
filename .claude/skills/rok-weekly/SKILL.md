---
name: rok-weekly
description: Process a week of Rise of Kingdoms 3514 alliance activity (fort destroyer + tech donation rankings from screenshots or screen recordings), update the offense tracker, and produce the weekly report, in-game mails and public dashboard. Also MGE (Mightiest Governor) point limits, takeovers and fines. Use when the user drops a new "weekly-activity/Activity <dates>" folder or an MGE ranking/allocation mail, says "process this week", marks accounts as farm/R4, records a paid fine, or changes the weekly or MGE rules.
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
| `tracker/fines_paid.csv` | `governor_id, name, week, gold_paid, note`. `week` = the Monday of the week the fine was issued, or `mge:<start>` for an MGE fine. Hand-entered payments only |
| `tracker/fines_online.csv` | Same columns, payments R4s marked on the dashboard; written by `track.py --pull` (generated) |
| `tracker/accounts_online.csv` | `governor_id, name, type, approved_by, proposed_by, decided`: approved farm/main changes (proposed by an R4 or a player; `approved_by` = the R4, approver or `admin` who decided); written by `track.py --pull`, overrides `accounts.csv` (generated) |
| `.github/workflows/recalc.yml` + `tracker/publish_ci.sh` | GitHub Action: `track.py --pull` and republish the dashboard. Started by the sheet on approval, hourly, or `gh workflow run recalc.yml`. Uses the `DASHBOARD_DEPLOY_KEY` secret; refuses to publish if the live dashboard has a week the repo lacks |
| `tracker/ledger.json` | Last pulled ledger: payments, account changes and SHA-256 of active R4 keys (never the keys). Published with the dashboard so R4 links work instantly even when the Google web app is slow; a rotated or new key works after the next pull (`publish.sh` or the hourly Action) (generated) |
| `tracker/fines_ledger/` | Apps Script (clasp project, owned by the Google account clasp is logged in as) bound to the "3514 Fines" Google Sheet: `Officers` tab = one personal dashboard key per R4, `Payments` tab = append-only payment log, `Accounts` tab = farm/main proposals (status proposed/approved/rejected; the admin, i.e. the user / sheet owner, not the R5, decides via the **3514** menu; approvers (`APPROVERS` in `Code.js` or `approver = yes` in Officers, e.g. Totos メtreme, ＡＧＡＭ) can approve/reject on the dashboard Review tab, and their own farm/main changes (single or multi-select in the master list) apply at once, which starts the Action using a GitHub token kept in Script Properties). `track.py` `FINES_URL` points at its web app |
| `tracker/reports/<monday>.md` | Weekly report (generated) |
| `tracker/mails/<monday>/` | In-game alliance mails, RoK rich text, each ≤ 2000 chars (generated) |
| `tracker/status.csv`, `tracker/offense_log.csv` | Current status and full offense history (generated) |
| `tracker/mge/` | MGE inputs: `mges.csv`, `<start>_slots.csv` (Top-10 allocation), `<start>.csv` (ranking). See **MGE** below |
| `tracker/mge_log.csv`, `tracker/reports/mge-<start>.md`, `tracker/mails/mge-<start>/` | MGE over-limit fines and takeovers, report, sanctions mail (generated) |
| `event/mge/<name (dates)>/` | Raw MGE ranking recordings / screenshots the user provides |
| `tracker/dashboard_template.html` → `tracker/dashboard/index.html` | Public dashboard (generated; `dashboard/` is its own git repo) |
| `tracker/publish.sh` | Rebuilds and pushes the dashboard to GitHub Pages |
| `weekly-activity/Activity <d-d mon yyyy>/` | Raw ranking screenshots / videos the user provides each week |
| `data-from-ingame/` | In-game member exports `3514_<from>_<to>_statsExport.xlsx` (see **New member export**) |

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
R4s can also propose farm/main on the dashboard; once an approver or the admin (the user) approves, `accounts_online.csv` overrides `accounts.csv`.
Players (no key) can **suggest** farm/main from the player pop-up (optional name and reason; `by = "player: <name>"` in the
Accounts tab); **any R4** can approve or reject those in Review. One open proposal per account, 100 open player suggestions
at most, 20 new per 10 minutes. Who decided is kept (`decided_by` in the sheet, `approvedBy` on the dashboard, `approved_by`
in `accounts_online.csv`) and shown in the pop-up: "Set as farm on <date> by <R4> (proposed by …)".
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

## MGE (Mightiest Governor)

Inputs in `tracker/mge/`: `mges.csv` (`mge` = start date, `start, end, troop, default_cap, final`), `<start>_slots.csv`
(`slot, name, governor_id, cap`: the Top-10 allocation from the leadership mail; blank cap = no cap) and `<start>.csv`
(`rank, governor_id, name, points`: final ranking). Raw recordings go in `event/mge/<name (dates)>/`.

Rules (`mge_results()` in `track.py`, fine rates `MGE_FINE`):
- A **slot holder** may go past their listed points as long as they finish at their slot (or lower). Finishing *above*
  their slot = took someone's rank: fined for the points over their listed cap.
- **Everyone else** (any alliance, farms and R4s included): max `default_cap` (7M). Fined for every point over.
  Finishing in a Top-10 rank allocated to someone else while over the limit is flagged as a **takeover**.
- Fine per point over: 1,000 food / 1,000 wood / 750 stone / 500 gold, one resource or a mix. Stored in gold value
  (500 gold per point) and paid through the same ledger as fort fines; R4s can type a mix like `300M food 50M gold`.
  Hand-entered payments go in `fines_paid.csv` with `week = mge:<start>`. The sanctions mail sends mixed payers to
  `MGE_CONTACTS` in `track.py` (ＡＧＡＭ, Totos メtreme) for the exact amounts.

Processing: add the row to `mges.csv` and the slots file (names exactly as in the mail), extract frames from the
recording (`extract_frames.py`; short fast-scrolling clips need `--fps 4`, else ranks are skipped), transcribe
`rank|name|points` into scratch, then `.venv/bin/python .claude/skills/rok-weekly/scripts/import_mge.py START ranking.txt`
(check `~~`/`--` lines; `--overrides` like `build_week.py`), `--write`, and `python3 tracker/track.py`.
Outputs: `reports/mge-<start>.md`, `mails/mge-<start>/1_results.txt` + `2_sanctions*.txt` (DRAFT banner until `final = yes`), `mge_log.csv`, the dashboard MGE tab.
Only the ranks captured are checked; capture until the points drop well below the default cap.
Names render in game with `✕` for `メ` (Totos ✕treme = Totos メtreme); transcribe with `メ`, the matcher folds both.

A ranking taken before the event ends is provisional: when the final one arrives, rerun `import_mge.py ... --write`
(it overwrites `<start>.csv`), set `final = yes` in `mges.csv` and run `track.py`. Until then the dashboard labels the
MGE provisional and R4s can't mark its fines paid. Don't hand over the sanctions mail from a provisional ranking.
The MGE tab, MGE fines and the pop-up's MGE section are **R4-only** for now (hidden for the public, though the numbers
are in the page source); to open them to everyone, drop the `officer` checks around `mgeTabBtn`, `shownFines()` and `p.mg`.

Report to the user: slot holders who held / fell below / took a higher slot, everyone over the limit with points over,
fine in gold and takeovers, players not matched to an ID, and whether every slot holder was captured. Point to the mail
folder, then ask before publishing.

Rule changes: the default cap is per event (`mges.csv`), Top-10 limits per event (slots file, from the leadership mail),
fine rates in `MGE_FINE` at the top of `track.py`.

## Dashboard tabs

Players (master list + player view; its search also finds **governors who left the kingdom**: anyone in an older scan,
name list or KvK sheet but not in the latest scan/export/rankings, kept with `x` = last date seen, listed under the
"Left the kingdom" filter; KvK history lists everyone in each KvK sheet with a Kingdom column, In kingdom / Migrated out) · Weekly activity · Fines (fort + MGE, with a **Fine calculator**, R4-only for now like the MGE tab (`calcCard` in `renderOfficer`): fine in
MGE points over or gold, plus what the player has in food/wood/stone/gold -> what is left, in each resource, with tap-to-fill "+ rest" suggestions under the empty fields; the MGE
sanctions mail links to it at `DASHBOARD_URL#t=fines`) · MGE · KvK history · Review (R4 mode only: proposals waiting for the admin,
and unconfirmed accounts in the alliance with farm hints from `farm_hints()` in `track.py`). Links: `#t=<tab>`, `#t=players&p=<name>`.
Future events (KvK, AoO, 20 GH…) get their own tab and data folder, sharing the master list, R4 keys and fines ledger.

## Processing a week

0. Python helpers need the project venv: `.venv/bin/python` (Pillow + openpyxl). If `.venv` is missing:
   `python3 -m venv .venv && .venv/bin/pip install pillow openpyxl`.
1. **Find the inputs** in the new `weekly-activity/Activity …` folder: fort ranking, tech ranking (skip "Resource Assistance"),
   and the newest member export `data-from-ingame/*_statsExport.xlsx` (Character ID, Username, Power…). The week's Monday is the file name.
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

- **Payment claims (players)**: on the Fines tab every unpaid fine has "I've paid: send proof" (when `CLAIMS_ON` in
  `track.py` is true). The player enters what they sent (a mix is fine) and attaches up to 20 screenshots/recordings, 30MB
  in total (`CLAIM` in `fines_ledger/Code.js`, mirrored as `CLAIM_*` in the template). Files go to a private Drive folder
  of the ledger's Google account; the claim is a row in the sheet's `Claims` tab. R4s see **Payment claims** on the Fines
  tab, view the proof and approve (appends a Payments row with the total paid, so it counts like "Mark paid") or reject
  with a reason the player sees. One waiting claim per fine, at most 5 per fine and 100 waiting overall, 20 new claims per
  10 minutes. A daily trigger (made by `setup()`) deletes proof files 30 days after the decision, and unfinished uploads
  after a day. The script needs the `drive.file` and `script.scriptapp` scopes: after changing them the ledger account
  must run `setup` once in the script editor to grant them, before `clasp update-deployment`.
- **Fine paid**: R4s mark payments on the dashboard with their personal `?key=` link ("Mark paid" opens a form with one
  field per resource, with tap-to-fill suggestions; recorded as gold value at the fine kind's rates); `publish.sh` pulls them.
  Only if the user reports one directly, append to `tracker/fines_paid.csv` (week = Monday the fine was issued, or
  `mge:<start>` for an MGE fine; `gold_paid` in gold value: food/wood ÷ 2, stone ÷ 1.5) and rerun.
- **Rule change**: edit the constants in `tracker/track.py`; the rules mail (`5_fort_rules.txt`) regenerates from them.
- **Fine exchange rates** are per kind of fine (`FINE_KINDS` in `track.py`: units of each resource worth 1 gold), because
  each event may set its own. Fort: 500K gold = 1M food/wood = 750K stone (gold per missing fort in `FORT_FINE`);
  MGE: derived from `MGE_FINE`. Each kind's `steps` are the rows of the calculator's rate table. A new event
  with fines adds its own entry and tags its fines with `t=<kind>` (MGE does `t='mge'`; fort fines have none). The
  calculator's "Fine for" list and the "Mark paid" conversion follow these rates.
- **Missing rank or wrong number** reported by the user: fix the week CSV row, rerun.

## Gotchas

- Helpers need `ffmpeg` (`brew install ffmpeg` if `extract_frames.py` says it is missing).
- WhatsApp recordings are 848×392; the default crop in `extract_frames.py` fits that layout. Other devices may need `--crop`.
- Ask for the original video or "send as document" — WhatsApp video compression can blur superscript tags.
- A week where only part of the ranking was captured is marked partial on the dashboard automatically
  (fewer than 90% of the usual player count). Players outside the captured ranks get no offense that week.
- `tracker/dashboard/` is a separate git repo (public). Commits there use the GitHub noreply address, never the work email.
