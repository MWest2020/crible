## 1. Discovery layer

- [x] 1.1 `discovery.py`: a `Discovery` with a pluggable backend interface returning candidate
      URLs (+title) for a query; cache per run; failures degrade (log + empty), never raise
- [x] 1.2 Backend: reddit's own search BLOCKS unauthenticated requests (verified 4xx), so the
      default backend is DuckDuckGo (no key) which SURFACES reddit + fora URLs (verified: it
      returns the exact lfcpyk thread); reddit thread pages are then client-fetchable. RedditBackend kept as an option.
- [x] 1.3 Config: `discovery_enabled` (default on), `discovery_backend` (default "duckduckgo"),
      `max_discovery_results`; env + CLI flags; documented defaults

## 2. Wire into retrieval

- [x] 2.1 Subagent: merge discovered URLs (query = candidate + disqualifier) with web_search
      sources before `_fetch_pages`
- [x] 2.2 Landscape: merge discovered community URLs into `_landscape_pages`
- [x] 2.3 Audit events: discovered URLs (backend, query, count) + backend degradation

## 3. Tests + docs

- [x] 3.1 Test: reddit backend parses thread URLs from a mocked search response
- [x] 3.2 Test: backend error degrades to empty (no raise), run continues
- [x] 3.3 Test: discovered URLs are merged into the retrieved source set
- [x] 3.4 ruff clean; `uv run pytest`
- [x] 3.5 README (discovery + flags) and CHANGELOG (dated entry)

## 4. Verify (free, on subscription)

- [x] 4.1 Run the thermos query; confirm reddit threads now appear and reach the advice.
      VERIFIED (2026-06-22, free subscription run): discovery surfaced 9 reddit URLs incl. the
      exact `lfcpyk` thread. First run exposed a second-half gap — `www.reddit.com` served our
      client a JS shell (10 pages = 37 chars, no findings). Fixed by fetching `old.reddit.com`
      (server-rendered). Re-run: reddit pages now 5.7k–30k chars and **5 findings cite reddit**
      with verbatim quotes (r/BuyItForLife, r/Coffee) shown in advice.md. Gap closed.
