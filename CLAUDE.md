# Context for Claude Code

Goal: daily-updated job board for remote design leadership roles in India. Owner prefers terse, direct output and no em dashes.

## State
- Built in a sandbox that blocks job sites, so NO source adapter has been run against live endpoints. Only `wanted()`, `scope_of()`, `remote_scope()`, `relative_to_ts()` and the template were tested.
- First task: run `python scrape.py`, read stderr, and fix adapters whose field names or endpoints are wrong.
- Himalayas field names (`locationRestrictions`, `applicationLink`, `pubDate`, `companyName`) were inferred from summarized output. Verify against the raw JSON.
- `companies.txt` tokens are unverified guesses. Failed boards are listed at the end of the ATS step. Prune or fix them.
- SerpApi free plan is 250 searches/month; `SERPAPI_MAX` (default 8) caps the daily run. Confirm the free plan includes the Google Jobs engine.
- A bare "Remote" on an ATS board is treated as worldwide, which can let US-only roles through. Consider tightening.
- Indeed and Naukri are not implemented (they block bots). LinkedIn is opt-in and against its terms.

## Rules
- Keep `board_template.html` renderable on its own (it has sample data fallback).
- Title filter lives in `DESIGN`, `LEVEL`, `NOISE` in scrape.py. Role buckets in the template's `roleOf()` must stay in sync.
