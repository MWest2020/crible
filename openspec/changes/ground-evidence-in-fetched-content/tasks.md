## 1. Fetch layer

- [x] 1.1 Client-side fetcher: httpx GET + minimal HTML→text extraction; cap content size;
      cache by URL per run; failures treated as dead (`fetch.py` `ContentFetcher`)
- [ ] 1.2 Server-side fetch on Anthropic via `web_fetch_20260209` — DEFERRED: Anthropic's UA
      can't crawl reddit (the point of fetching), so client fetch is primary; server fetch is a
      future add for crawlable pages
- [x] 1.3 Config `fetch_enabled` (default on), `max_fetch_pages_per_finding`, `max_fetch_chars`,
      `quote_match_ratio`; env (`CRIBLE_FETCH`, `CRIBLE_QUOTE_MATCH_RATIO`) + CLI

## 2. Quote verification

- [x] 2.1 Quote-matching util: normalise + exact-substring OR token-overlap ≥ ratio (`fetch.py`)
- [ ] 2.2 Feed fetched page text INTO extraction — PARTIAL: we verify the model's quote against
      fetched text post-hoc (drops unverifiable); pre-fetch-then-extract is a future refinement
- [x] 2.3 Verify each finding's quote against its cited fetched pages; drop unverifiable
      findings; subsume link-liveness for fetched sources (`_ground_finding`)

## 3. Degradation + audit

- [x] 3.1 Degrade to link-liveness when fetch is disabled; never fail the run
- [x] 3.2 Audit events: `fetch` (url, ok, chars), `quote_check` (matched, score), drops

## 4. Tests + docs

- [x] 4.1 Test: quote present in fetched text → kept; absent → finding dropped
- [x] 4.2 Test: unfetchable page treated as dead
- [x] 4.3 Test: fetch disabled → falls back to link-liveness
- [x] 4.4 Test: match util (normalised substring + token-overlap threshold)
- [x] 4.5 ruff clean; `uv run pytest` (33 passing)
- [x] 4.6 README (fetch/verify + forum-discovery) and CHANGELOG (dated entry)
