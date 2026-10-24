# Kingdom 3514 – Weekly Activity Tracker

Tracks the weekly **barbarian fort** and **tech donation** activity of the main alliance
[14-X] in Rise of Kingdoms kingdom 3514. It checks every player against the weekly
minimums, counts offenses, calculates fines, and produces a report, in-game alliance
mails and a public dashboard.

**Dashboard:** https://rizkyekoputra.github.io/rok-3514-dashboard/

## Weekly rules

| | |
|---|---|
| Minimum | **70 forts** and **50,000 tech** per week |
| 1st offense | Forgiven + Low Contribution label |
| 2nd offense | 500K gold × missing forts |
| 3rd offense | 1M gold × missing forts + unpaid fines |
| 4th offense | Must migrate, or the account is zeroed |
| Clearance | Reach 70 forts **2 weeks in a row** to wipe all offenses (history is kept) |
| Fine payment | Bank KD account **KINGDOM 3514** (500K gold = 1M food / 1M wood / 750K stone) |

- Fort penalties apply to every **main account**, including R4 and R5. **Farms never get penalties.**
- Tech donation has no penalty; low donors are listed in the report.
- **Rewards** go to the top 10 main accounts by forts (farms, R4 and R5 excluded):
  1st Legendary Trophy + 10K VIP (+ $5 Flux with 200+ forts) · 2nd Epic Trophy + 5K VIP ·
  3rd Epic Trophy · 4th–8th Elite Trophy · 9th–10th Advanced Trophy · every R4 gets an Advanced Trophy.
- Fort counts are per player. A fort destroyed in a rally counts for every participant, so the
  alliance sum is "fort credits", not unique forts.

The numbers live as constants at the top of [`tracker/track.py`](tracker/track.py).

## MGE (Mightiest Governor)

Kingdom Leadership allocates the Top 10 slots, each with a listed point limit; everyone else may score at most **7M**.

- Top-10 slot holders may go past their listed points **as long as they finish at their slot**. Finishing above it
  (taking someone else's rank) is fined for the points over their limit.
- Everyone else is fined for every point over 7M. Finishing in someone else's Top-10 rank is marked as a **takeover**.
- Fine per point over: **1,000 food / 1,000 wood / 750 stone / 500 gold**, in one resource or a mix, paid to
  **KINGDOM 3514**. R4s mark payments on the dashboard (gold, or a mix like `300M food 50M gold`).

Drop the ranking recording in `event/mge/<name (dates)>/` with the allocation mail and ask Claude to process the MGE.
Inputs live in `tracker/mge/`; results are in `tracker/reports/mge-<start>.md`, `tracker/mails/mge-<start>/` and the
dashboard's MGE tab.

## Every week

1. **Before the weekly reset**, screen-record (or screenshot) the **Fort Destroyer** and
   **Mad Scientist** (tech) rankings from rank 1 to the last rank. Scroll slowly.
   An in-game member export (`*_statsExport.xlsx`, kept in `data-from-ingame/`) helps match renamed players.
2. Put the files in a new folder under `weekly-activity/`, e.g. `weekly-activity/Activity 19-25 oct 2026/`.
3. In Claude Code, opened in this folder, say **"process this week"**. The
   [`rok-weekly`](.claude/skills/rok-weekly/SKILL.md) skill reads the rankings, matches names to
   Governor IDs, runs the tracker and summarises the results.
4. Send the mails from `tracker/mails/<week>/` in-game.
5. Publish the dashboard: `sh tracker/publish.sh`.

Tell Claude when an account is a farm or R4, or when someone pays a fine; it updates the account list or
payment log and recalculates everything.

## What's in here

| Path | Contents |
|---|---|
| `tracker/track.py` | The calculator. Rebuilds everything below from the inputs |
| `tracker/accounts.csv` | Every account: Governor ID, name, main/farm, R4/R5, previous names |
| `tracker/weeks/<monday>.csv` | One file per week: fort and tech rank and value per player |
| `tracker/fines_paid.csv` | Fines that have been paid |
| `tracker/mge/` | MGE events, Top-10 allocations and final rankings |
| `tracker/reports/<monday>.md` | Weekly report: summary, rewards, penalties, low tech, farms |
| `tracker/mails/<monday>/` | In-game mails (RoK rich text, max 2,000 characters each) |
| `tracker/status.csv` | Each player's current offenses, passing streak and unpaid fines |
| `tracker/offense_log.csv` | Every offense and clearance ever recorded |
| `tracker/dashboard_template.html` | Dashboard page; filled with data by `track.py` |
| `tracker/publish.sh` | Pushes the dashboard to GitHub Pages |
| `.claude/skills/rok-weekly/` | Claude Code skill and helper scripts (video frames, name matching) |
| `weekly-activity/Activity …/` | Raw fort/tech ranking screenshots and recordings per week |
| `event/<event>/<name (dates)>/` | Raw event rankings, e.g. `event/mge/mge-infa (19-24 oct 2026)/` |
| `data-from-ingame/` | In-game member exports (`3514_<from>_<to>_statsExport.xlsx`) |
| `3514 Ch25.xlsx`, `TOP500-…xlsx`, `3514_*.csv` | Ch25 roster and kingdom scans with the derived CSVs |

Generated files (`reports/`, `mails/`, `status.csv`, `offense_log.csv`, `dashboard/`) should not be
edited by hand; change the inputs and run `python3 tracker/track.py`.

## Setup

- Python 3 (the tracker itself needs nothing else).
- Helper scripts need a virtual environment and `ffmpeg`:
  ```bash
  python3 -m venv .venv && .venv/bin/pip install pillow openpyxl
  brew install ffmpeg
  ```
- Publishing needs the GitHub CLI logged in (`gh auth login`).

`tracker/dashboard/` is a separate public repository
([rok-3514-dashboard](https://github.com/rizkyekoputra/rok-3514-dashboard)) and is not part of this one.
It only contains the generated page: player names and weekly numbers, no Governor IDs.
