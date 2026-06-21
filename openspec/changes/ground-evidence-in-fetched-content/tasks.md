## 1. Fetch layer

- [ ] 1.1 Client-side fetcher: httpx GET + minimal HTML→text extraction; cap content size;
      cache by URL per run; failures treated as dead
- [ ] 1.2 Server-side fetch on Anthropic via `web_fetch_20260209` where available
- [ ] 1.3 Config `fetch_enabled` (default on), `max_fetch_pages_per_finding`, `max_fetch_chars`,
      `quote_match_ratio`, optional fetch-IO concurrency; env + CLI; documented defaults

## 2. Quote verification

- [ ] 2.1 Quote-matching util: normalise (whitespace/case/quotes), exact-substring OR
      token-overlap ≥ ratio
- [ ] 2.2 Feed fetched page text into finding extraction (quotes drawn from real content)
- [ ] 2.3 Verify each finding's quote against its cited fetched pages; drop unverifiable
      findings; subsume link-liveness for fetched sources

## 3. Degradation + audit

- [ ] 3.1 Degrade server→client→link-liveness with a logged note; never fail the run
- [ ] 3.2 Audit events: page fetched, quote-match (page, matched?, score), drops

## 4. Tests + docs

- [ ] 4.1 Test: quote present in fetched text → kept; absent → finding dropped
- [ ] 4.2 Test: unfetchable page treated as dead
- [ ] 4.3 Test: fetch disabled → falls back to link-liveness + instructed quote
- [ ] 4.4 Test: match util (normalised substring + token-overlap threshold)
- [ ] 4.5 ruff clean; `uv run pytest`
- [ ] 4.6 README (fetch/verify behaviour + flags) and CHANGELOG (dated entry)
