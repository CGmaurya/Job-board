# Design leadership job board (remote, India)

Scrapes Principal, Staff, Director / Head, UX Manager and UX Lead design roles that are remote in India
or worldwide-remote and open to India. Builds a filterable `board.html`.

## Run locally

    pip install -r requirements.txt
    export SERPAPI_KEY=...        # optional, Google Jobs via SerpApi (free: 250 searches/month)
    python scrape.py              # writes jobs.json and board.html
    python scrape.py --linkedin   # optional, best effort, against LinkedIn's terms of use, off by default

Open `board.html` (not `board_template.html`, which only shows sample rows).

## Run daily

`.github/workflows/daily.yml` runs at 09:00 IST, commits `jobs.json`, and publishes `board.html` to GitHub Pages.
Setup: add repo secret `SERPAPI_KEY`, set Settings > Pages > Source to "GitHub Actions", then run the workflow once by hand.

## Files

- `scrape.py`: sources (Himalayas, Remotive, RemoteOK, Jobicy, We Work Remotely, Greenhouse/Lever/Ashby, SerpApi), title filter, dedupe, 14 day carry-over
- `companies.txt`: career boards as `ats:token`
- `board_template.html`: the page, data injected into the `#data` JSON tag
- `jobs.json`: last run output, seeded with 11 real listings from 2026-09-19
