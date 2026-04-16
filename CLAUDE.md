# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Generates a weekly read-only HTML brief (`output/index.html`) for UGC creators at **yourTMJ** (a jaw/TMJ wellness device brand). It pulls top-performing Meta ads + manually curated external inspiration, auto-tags them by creative format, and renders them via a Jinja2 template.

## Running the generator

```bash
# API mode (default) — pulls live data from Meta Marketing API
python generate.py

# CSV mode — uses local data/meta_ads.csv (no credentials needed)
python generate.py --source csv

# Specify week or limit ads shown
python generate.py --week 2026-W15
python generate.py --top 10        # default is 5

# Include Trello content ideas (requires TRELLO_* env vars, see below)
python generate.py --trello
python generate.py --trello --trello-limit 8   # show up to 8 cards (default: 5)

# Open the output
open output/index.html
```

Install dependencies once: `pip install -r requirements.txt`

## Environment variables (`.env`)

```
META_ACCESS_TOKEN=...       # Long-lived token (~60 days), see below for refresh
META_AD_ACCOUNT_ID=act_...
META_APP_ID=...
META_APP_SECRET=...
META_DATE_PRESET=last_7d    # optional, default: last_7d
META_API_VERSION=v21.0      # optional

TRELLO_API_KEY=...          # from trello.com/power-ups/admin
TRELLO_TOKEN=...            # from trello.com/power-ups/admin
TRELLO_BOARD_ID=...         # short code in board URL: trello.com/b/BOARD_ID/...
```

**Refreshing the token:** The Meta access token expires every ~60 days. To refresh:
1. Get a new short-lived token from `developers.facebook.com/tools/explorer`
2. Run this Python snippet to exchange it for a 60-day token:
```python
import urllib.request, urllib.parse, json
params = urllib.parse.urlencode({
    'grant_type': 'fb_exchange_token',
    'client_id': META_APP_ID,
    'client_secret': META_APP_SECRET,
    'fb_exchange_token': SHORT_LIVED_TOKEN,
})
url = 'https://graph.facebook.com/oauth/access_token?' + params
with urllib.request.urlopen(url) as r:
    print(json.loads(r.read()))
```
3. Update `META_ACCESS_TOKEN` in `.env` with the returned `access_token`.

## Architecture

**Entry point:** `generate.py` — orchestrates steps: load Meta ads → load external inspo → (optionally) load Trello ideas → load brief → render HTML.

**Data flow:**
```
Meta API or CSV  ──►  adapter  ──►  ContentItem  ──►  page_generator  ──►  output/index.html
external CSV     ──►  adapter  ──►  ContentItem  ──┤         ▲
Trello API       ──►  adapter  ──►  ContentItem  ──┘         │
data/brief.json  ─────────────────────────────────────────────┘
```

**Key design decisions:**
- `ContentItem` (`schema.py`) is the single shared data model. All adapters produce lists of these; the template consumes them.
- Ads are filtered to only those with 7-day activity, then ranked by `results_7d`. Lifetime results (`results_total`) are fetched separately and displayed alongside for context.
- `tagger.py` auto-tags based on keyword rules. Tags flow into the template as pill badges. Edit `RULES` in `tagger.py` to add/change creative format tags.
- The brief (`data/brief.json`) is hand-edited each week before running. It has 4 required keys: `what_is_working`, `patterns`, `themes`, `external_spotlight`.
- `report_builder.py` loads and validates `brief.json` but does not generate content — all editorial copy is written manually.

**Template:** `templates/weekly.html` is a single self-contained Jinja2 file with inline CSS. Meta ad cards show `results_7d` and `results_total`. External inspiration cards show `notes` instead of metrics. Trello idea cards show `notes` (card description) and a "Has Example" badge if the card contains a non-Trello URL.

**Video playback (live and working):** Meta ad cards with a `video_url` display the thumbnail with a white play button overlay. Clicking replaces the thumbnail with an inline HTML5 `<video>` player — no new tab, no redirect. The video URL is a direct CDN MP4 fetched from the Meta API at generation time. These URLs expire in ~24–48 hours, which is fine since the brief is regenerated weekly. Video fetching only runs for the top 10 ads to avoid excessive API calls. The `ContentItem` schema has a `video_url` field (default empty); the CSV adapter also accepts an optional `video_url` column for manual overrides.

## Weekly workflow

1. Edit `data/brief.json` with this week's narrative
2. Optionally update `data/external_inspo.csv`
3. Run `python generate.py` (add `--trello` once Trello access is set up)
4. Open and share `output/index.html`

## CSV column reference

`data/meta_ads.csv`: `ad_id, ad_name, ad_url, thumbnail_url, gmv, views, spend, description, tags, results_7d, results_total, video_url` (video_url optional — leave blank to skip inline playback)

`data/external_inspo.csv`: `title, url, thumbnail_url, notes, tags`

Tags in CSVs are semicolon-separated (e.g. `before_after;hook;ugc`). If omitted, `tagger.py` infers them from title/description text.

## DO NOT CHANGE — locked implementations

These sections have been debugged and fixed multiple times. Do not modify them unless there is a clearly diagnosed, specific reason to do so.

### `adapters/meta_api.py` — `_fetch_ads` creative fields

The `fields` parameter in `_fetch_ads` is:
```python
"fields": "id,name,status,creative{id,body,title,image_url,thumbnail_url}"
```

**Do not add `object_story_spec` or any other nested field.** It was removed because it causes a 400 error from the Meta API. This has been broken and re-fixed at least three times. If the API call fails, diagnose the actual error before touching this line.

### `generate.py` — Meta API rate limit handling

When the Meta API returns a 400 with error code `80004`, the script exits cleanly with a human-readable message instead of crashing with a stack trace. This prevents the brief from being generated with placeholder CSV data as a workaround. Do not remove this error handling or add a CSV fallback.

### `adapters/newsletter_scrape.py` — beehiiv scraper

The beehiiv newsletter scraper is opt-in via `--newsletter` flag. It is working correctly and does not need changes. The `data/meta_ads.csv` file contains **placeholder/sample data only** — it is not real ad data. Always run `python generate.py --newsletter` (API mode, no `--source csv`) to get real Meta ads.

---

## Trello integration

**Status: built, pending API access.**

`adapters/trello.py` is fully implemented but cannot be tested until the Trello credentials are in `.env`. The integration works as follows:

- Fetches all open cards from the board specified by `TRELLO_BOARD_ID`
- Filters to cards with the **"Ads"** label (case-insensitive)
- Sorts so cards containing a URL in their description or an image attachment appear first ("Has Example" badge shown in the UI)
- Maps each card to a `ContentItem` with `source="trello"`, using the card name as title, description as notes, and first image attachment as thumbnail
- Renders in a "Founder's Content Ideas" section in the HTML brief

**Status: ready to test.** Lauren is now an admin on the board. Credentials needed in `.env`: `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`. Get key + token at `trello.com/power-ups/admin`; Board ID is the short code in the board URL (`trello.com/b/BOARD_ID/...`).
