## 1. Live-link grounding

- [x] 1.1 Add `LinkChecker` (`links.py`): HEAD/GET probe, cache per run; 404/410/unreachable =
      dead, 401/403/429 = live (page exists)
- [x] 1.2 Config `verify_links` (default on) + `link_check_timeout`, with env vars
- [x] 1.3 In extraction, drop dead-link sources; drop a finding with no live source; log drops
- [x] 1.4 Add `httpx` as a direct dependency via `uv`

## 2. Verbatim quotes

- [x] 2.1 Add `Finding.quote`; add `quote` to the findings schema (required) + subagent prompt
- [x] 2.2 Render the quote under each claim in the advice

## 3. Tests + docs

- [x] 3.1 Test: dead/unreachable links dropped, 403 kept
- [x] 3.2 Test: finding with only dead links is dropped
- [x] 3.3 Test: quote is rendered in advice
- [x] 3.4 ruff clean; `uv run pytest` (28 passing)
- [x] 3.5 CHANGELOG dated entry (README behaviour already covers advice format)
