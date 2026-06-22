## 1. Discovery layer

- [ ] 1.1 `discovery.py`: a `Discovery` with a pluggable backend interface returning candidate
      URLs (+title) for a query; cache per run; failures degrade (log + empty), never raise
- [ ] 1.2 Reddit backend: query reddit search, extract thread permalinks (browser UA;
      handle 403/429 by degrading)
- [ ] 1.3 Config: `discovery_enabled` (default on), `discovery_backend` (default "reddit"),
      `max_discovery_results`; env + CLI flags; documented defaults

## 2. Wire into retrieval

- [ ] 2.1 Subagent: merge discovered URLs (query = candidate + disqualifier) with web_search
      sources before `_fetch_pages`
- [ ] 2.2 Landscape: merge discovered community URLs into `_landscape_pages`
- [ ] 2.3 Audit events: discovered URLs (backend, query, count) + backend degradation

## 3. Tests + docs

- [ ] 3.1 Test: reddit backend parses thread URLs from a mocked search response
- [ ] 3.2 Test: backend error degrades to empty (no raise), run continues
- [ ] 3.3 Test: discovered URLs are merged into the retrieved source set
- [ ] 3.4 ruff clean; `uv run pytest`
- [ ] 3.5 README (discovery + flags) and CHANGELOG (dated entry)

## 4. Verify (free, on subscription)

- [ ] 4.1 Run the thermos query; confirm reddit threads now appear in source_visited and the
      advice (the reddit gap closed)
