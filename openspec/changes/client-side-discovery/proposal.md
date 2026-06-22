## Why

Measured across every run so far: **1181 visited sources, 0 from reddit.** Anthropic's
`web_search` never surfaces reddit — its crawler is blocked there, so reddit URLs don't come
back at all. Yet reddit is the single most-wanted source (the whole "append reddit to your
search" desire-path the product exists to serve), and a plain Google query surfaces the exact
on-topic thread instantly. The gap is **discovery, not fetching**: our own client can already
read reddit (verified HTTP 200), we just never get the URLs.

This change adds a **client-side discovery layer** that finds URLs the provider's web_search
misses — starting with reddit — and feeds them into the existing client-fetch + quote-
verification pipeline, so genuine reddit/forum lived experience finally reaches the advice.

## What Changes

- **NEW client-side discovery.** A pluggable discovery step that, given a query, returns
  candidate URLs from sources the provider can't surface. First backend: **reddit** (query
  reddit's own search, extract thread permalinks). The backend interface allows adding general
  search engines (Brave / Tavily / SearXNG) later (keys via config).
- **Augment, don't replace.** Discovery results are MERGED with the provider's web_search
  results in both the landscape (candidate discovery) and subagent (evidence) stages, then run
  through the existing fetch + classify + quote-verify path. Reddit classifies high-trust and
  is client-fetchable, so reddit threads become first-class evidence.
- **Bounded, logged, degradable.** Discovery is bounded (max results/query, cached), every
  discovered URL is logged, and a backend failure (rate-limit/block) is logged and the run
  continues on web_search alone — never fails.
- **Config.** `discovery_enabled` (default on), `discovery_backend`, `max_discovery_results`,
  via `CRIBLE_*` + CLI, with documented defaults.

## Capabilities

### New Capabilities

- `client-discovery`: a client-side, pluggable discovery layer that surfaces URLs (esp. reddit
  and fora) the provider's web_search misses, bounded and logged, feeding the existing
  client-fetch pipeline.

### Modified Capabilities

- `orchestration`: landscape and subagent retrieval augment provider web_search results with
  client-discovered URLs before fetch/extract.

## Impact

- **Code** (this change): `discovery.py` (backend interface + reddit backend), wiring in
  `orchestrator.py` (landscape + subagent), `config.py`/`cli.py` knobs, audit events for
  discovered URLs and backend degradation.
- **Relationship to other changes**: this is the cloud-path complement to
  `support-local-sovereign-models`' `pluggable-search` (which targets local-model retrieval) —
  here we *augment* provider search to fix the reddit gap, reusing the client-fetch from
  `ground-evidence-in-fetched-content`.
- **Cost**: bounded HTTP discovery calls (cached); on subscription, free. No extra LLM tokens
  beyond feeding discovered pages to the existing extraction.
- **Risk**: reddit may rate-limit/block unauthenticated discovery; handled by graceful
  degradation + the option of a keyed general backend.
- **Conventions**: uv only; EUPL-1.2 SPDX header on `discovery.py`; no learned scoring; fully
  auditable; single-threaded.
