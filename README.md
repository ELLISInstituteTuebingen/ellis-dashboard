# ELLIS Institute Tübingen — Research Dashboard

An automatically-updating dashboard of publications and inter-ELLIS-Unit
collaboration, built on the free [OpenAlex](https://openalex.org) API.

**Live demo data is already in `docs/data/publications.json`** (fictional
sample scientists) so you can see the dashboard working before connecting
your real team. Open `docs/index.html` in a browser to preview it now.

## How it works

```
config/team.json           <- your scientists + OpenAlex Author IDs
config/ellis_units.json    <- other ELLIS Units + their OpenAlex Institution IDs
scripts/fetch_data.py      <- pulls data from OpenAlex, writes docs/data/publications.json
docs/                      <- the static dashboard (HTML/CSS/JS), served by GitHub Pages
.github/workflows/         <- scheduled job that re-runs the fetch and redeploys
```

Every week (or whatever schedule you set), GitHub Actions runs
`fetch_data.py`, which:
1. Fetches every publication for each scientist in `team.json` from OpenAlex.
2. Deduplicates papers co-authored by multiple of your scientists.
3. Checks each paper's co-author institutions against `ellis_units.json` to
   count collaborations with other ELLIS Units.
4. Writes the result to `docs/data/publications.json`.
5. Commits the change and redeploys the GitHub Pages site.

## Setup (one-time)

### 1. Find your scientists' OpenAlex Author IDs
For each person, search:
```
https://api.openalex.org/authors?search=Their+Full+Name
```
Copy the `id` field (e.g. `https://openalex.org/A5023456789` → `A5023456789`)
from the correct match — check their `last_known_institutions` to be sure you
picked the right person if the name is common. Fill these into
`config/team.json`.

### 2. Find institution IDs for the ELLIS Units you want to track
```
https://api.openalex.org/institutions?search=University+Name
```
Fill these into `config/ellis_units.json`. Check https://ellis.eu/units for
the current list of Units and their host institutions.

### 3. Push to GitHub
Create a repo, push this folder to the `main` branch.

### 4. Enable GitHub Pages
Repo Settings → Pages → Source: **GitHub Actions**.

### 5. Run it
Either wait for the Monday schedule, or trigger it immediately:
Actions tab → "Update dashboard data" → **Run workflow**.

Your dashboard will then be live at
`https://<your-org>.github.io/<repo-name>/`.

## Running locally

```bash
pip install -r requirements.txt
python scripts/fetch_data.py
# then just open docs/index.html in a browser
```

## Customizing the schedule

Edit the `cron` line in `.github/workflows/update-dashboard.yml`.
Use https://crontab.guru to build the expression — e.g. `0 5 * * *` for daily.

## Extending it

- **More data sources**: Semantic Scholar and DBLP both have free APIs with
  no key required if you want to cross-check OpenAlex coverage.
- **Per-scientist pages**: the JSON already tracks which scientist(s) authored
  each paper — easy to add a filtered view per person.
- **Citation trend, not just count trend**: `publications_per_year` could be
  extended to `citations_per_year` with a small change to `fetch_data.py`.
