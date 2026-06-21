## Why

The worked-example runs (Haiku 4.5, the thermos question) confirmed a source-quality
problem: retrieval is blog/affiliate-dominated and surfaces too few specialist fora and
user reviews. Ten sources from an SEO echo chamber are worth less than one good forum
thread plus ten user reviews.

The deterministic ranker is fine, and a prior change already made corroboration
credible-only (low-tier excluded) and added `blocked_domains` on the open search pass.
But the **input is still contaminated**: `web_search` in `src/crible/llm.py` runs largely
unsteered (only `max_uses` + a blocklist), and `source_tiers.yaml` classifies *after the
fact* — nothing actively steers retrieval *toward* high/medium-trust sources. And there is
no floor guaranteeing enough trustworthy evidence before a verdict, so a clean "Avoid"
section is ambiguous between "nothing failed" and "we never found trustworthy enough
sources to judge". This change fixes the retrieval input and makes the evidence sufficiency
explicit and logged.

## What Changes

- **Domain-steered search (dual pass).** Wire `web_search` `allowed_domains` /
  `blocked_domains` from `source_tiers.yaml`:
  - a dedicated **high-trust pass** that allow-lists the domain-listed fora + review
    platforms, and
  - the existing **open pass** that block-lists known affiliate/blog domains.
  - **Stated limitation:** `allowed_domains` filters by domain, so it only covers the
    explicitly domain-listed high/medium sources — NOT the regex/path-based forum rules.
    The design works around this with the dedicated pass *plus* query augmentation, rather
    than pretending `allowed_domains` covers everything high-tier.
- **Forum/review-targeted query augmentation.** For each subagent search, deterministically
  template queries toward lived experience (the "reddit" desire-path, `site:` operators for
  the listed specialist fora, "review"/"long-term" phrasing). The templates applied are
  logged.
- **An explicit, configurable, LOGGED evidence-mix floor.**
  - Low-tier sources do NOT count as corroboration — they may yield leads, never evidence.
  - If the high+medium source count for a finding/candidate is below a configurable floor,
    trigger ONE bounded targeted high-trust re-search.
  - If the floor is still not met after that, proceed but emit a loud, logged
    `evidence-mix-floor-not-met` caveat that the final advice MUST surface — never a silent
    pass. A clean "Avoid" section must never be ambiguous between "nothing failed" and
    "insufficient trustworthy sources".
- **New audit event types**: domains allowed/blocked per search, query templates applied,
  per-finding source-tier mix, floor checks, and any floor-not-met caveat — so the run stays
  fully reconstructable from `audit.jsonl`.
- **Configuration**: everything new is exposed via `CRIBLE_*` env vars + CLI flags with
  documented defaults; the floor and the re-search bound are config, not magic numbers.
- **Single-threaded and bounded.** This REDUCES wasted tokens on blogs; the targeted
  re-search is exactly one extra pass, never a loop. No parallel multiplier.

## Capabilities

### New Capabilities

- `evidence-mix`: low-tier-never-corroborates rule, the configurable evidence-mix floor, the
  one bounded high-trust re-search, the loud floor-not-met caveat, and the advice
  disambiguation between "nothing failed" and "insufficient trustworthy sources".

### Modified Capabilities

- `orchestration`: adds domain-steered dual-pass search and deterministic forum/review query
  augmentation (with the `allowed_domains` limitation handled explicitly).
- `source-classification`: the seed tier list additionally exposes explicit domain
  allow/block lists for retrieval steering, kept separate from the regex/path rules; every
  steering decision traces to the seed list (no learned scoring).

## Impact

- **Code** (implementation deferred to apply): `config.py` (floor, re-search bound, steering
  toggles, query-template config), `sources.py` (extract domain allow/block lists from the
  tier list), `llm.py` (pass `allowed_domains`/`blocked_domains`; expose a targeted pass),
  `orchestrator.py` (dual-pass search, query augmentation, floor check + bounded re-search,
  caveat), `advice.py` (surface the caveat + disambiguate the Avoid section), `audit.py`
  (new event types), `cli.py` (flags).
- **Config/data**: `config/source_tiers.yaml` is the single source of the domain lists used
  for steering (no new trust source).
- **Cost**: intended net reduction in blog tokens; adds at most one bounded re-search per
  under-evidenced finding/candidate.
- **Docs**: `README.md` (new flags/env vars + behaviour) and `CHANGELOG.md` updated in the
  same change.
- **Conventions**: uv only (never pip); EUPL-1.2 SPDX headers on any new file; no
  learned/black-box scoring.
