# MSI 2026 Knockouts Calendar

A calendar generator for League of Legends MSI 2026 knockout matches. It scrapes match data from the official [LoL Esports](https://lolesports.com) website, builds a JSON database, and publishes an ICS calendar file suitable for subscription.

Match data is sourced from the [MSI 2026 Knockouts bracket](https://lolesports.com/en-US/tournament/115570934354631452/stage/115570934355090206).

## Overview

Subscribe to get all **14 MSI 2026 knockout matches** in your calendar. Pending opponents are shown as `TBD` and update automatically after earlier rounds finish.

**Subscription URL** (copy this):

```
https://cdn.jsdelivr.net/gh/pl0327/LOL_MSI26_Calendar@master/msi_2026.ics
```

## Features

- **14 knockout matches** across upper bracket, lower bracket, and finals (play-ins excluded)
- **JSON database** (`data/matches.json`) with structured match metadata
- **ICS calendar** (`msi_2026.ics`) for calendar apps
- **Auto-updating opponents** — `TBD` slots are resolved to actual team names once lolesports.com publishes results
- **GitHub Actions** — hourly checks during the tournament, committing updates automatically
- **GitHub Pages** — hosts the ICS at a public URL for calendar subscription

## Repository layout

```
├── src/
│   └── generate_calendar.py   # Scrape lolesports.com and generate outputs
├── data/
│   └── matches.json           # JSON match database
├── docs/
│   └── msi_2026.ics           # ICS copy for GitHub Pages
├── msi_2026.ics               # ICS calendar (repo root)
└── .github/workflows/
    └── update-calendar.yml    # Scheduled auto-update workflow
```

## Requirements

- Python 3.9+ (uses standard library only — no pip dependencies)

## Usage

### Generate or refresh the calendar

```bash
python src/generate_calendar.py --force
```

This scrapes the latest data from lolesports.com and writes:

- `data/matches.json`
- `msi_2026.ics`
- `docs/msi_2026.ics`

### Smart update (used by GitHub Actions)

```bash
python src/generate_calendar.py --auto
```

`--auto` only fetches when:

1. At least one match is in a post-match update window (**start + 3 hours** or **start + 6 hours**), and
2. Scraped data has actually changed (e.g. a knockout opponent updated from `TBD` to a team name)

Before any match reaches its first update window, `--auto` skips the scrape entirely.

## Event format

Each calendar event looks like:

```
SUMMARY: UPPER 1 - HLE vs TSW
```

Match phases: `UPPER 1`, `UPPER 2`, `UPPER 3`, `LOWER 1`, `LOWER 2`, `LOWER 3`, `LOWER 4`, `FINALS`.

Event titles use short team codes (as shown on lolesports.com). Notes include the full round name and full team names:

```
League of Legends MSI 2026 Knockouts
Upper Bracket - Round 1
Hanwha Life Esports vs Team Secret Whales

Schedule: https://lolesports.com/en-US/leagues/first_stand,msi,worlds

Bracket: https://lolesports.com/en-US/tournament/115570934354631452/stage/115570934355090206
```

For knockout rounds, opponents not yet decided are shown as `TBD`. These are updated automatically once the feeding match result is available.

Each event links to the [LoL Esports YouTube channel](https://www.youtube.com/@lolesports) for live streams. Times are in **Korean Standard Time** (`Asia/Seoul`, GMT+9).

## GitHub setup

### 1. Enable GitHub Pages

GitHub Pages serves the ICS file from the `docs/` folder so it is available at a stable public URL.

1. Open the repo on GitHub → **Settings** → **Pages**
2. Under **Build and deployment** → **Source**, choose **Deploy from a branch**
3. Set **Branch** to `master` and **Folder** to `/docs`
4. Save

After the first deployment, the calendar is available at:

```
https://pl0327.github.io/LOL_MSI26_Calendar/msi_2026.ics
```

Use the same URL with a `webcal://` prefix if your calendar app expects a subscription link.

### 2. Enable GitHub Actions

The auto-update workflow lives at `.github/workflows/update-calendar.yml`. GitHub Actions is enabled by default on most repos. To confirm:

1. Go to **Settings** → **Actions** → **General**
2. Allow actions to run (e.g. **Allow all actions and reusable workflows**)
3. Under **Workflow permissions**, choose **Read and write permissions** so the workflow can commit updated files

### 3. Initial calendar publish

Generate the calendar locally and push, or run the workflow once from GitHub:

```bash
python src/generate_calendar.py --force
git add data/matches.json msi_2026.ics docs/msi_2026.ics
git commit -m "Publish MSI 2026 knockout calendar"
git push
```

Alternatively: **Actions** → **Update MSI Calendar** → **Run workflow** (requires `data/matches.json` to already exist in the repo for `--auto` to compare changes; use a local `--force` run for the first publish).

## Auto-update workflow

The [Update MSI Calendar](.github/workflows/update-calendar.yml) workflow:

- Runs **every hour** on a cron schedule
- Can also be triggered manually via **Actions → Update MSI Calendar → Run workflow**
- Runs `python src/generate_calendar.py --auto`
- Commits and pushes only when match data or the ICS file has changed

Updates are triggered twice after each match — at **start + 3 hours** and **start + 6 hours** — giving lolesports.com time to publish results before downstream knockout opponents are updated.

## Data source

Match data is scraped from the official lolesports.com knockouts page (embedded bracket data in the page HTML):

```
https://lolesports.com/en-US/tournament/115570934354631452/stage/115570934355090206
```

Stable UIDs (`msi26-knockout-{matchId}@msi-calendar`) ensure that updated events merge correctly in subscribed calendars instead of creating duplicates.
