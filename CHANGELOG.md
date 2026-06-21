# Changelog

All notable changes to this project are documented here. Dates are ISO 8601.

## [Unreleased]

### 2026-06-21 — Initial OpenSpec proposal

- Initialised repository: Python/`uv` + EUPL-1.2 + OpenSpec-first conventions.
- Scaffolded OpenSpec (CLI 1.3.0, schema `spec-driven`) and `openspec/project.md`.
- Added change proposal `add-bias-correcting-research-agent`:
  - `proposal.md` — Why (bias problem + the "reddit" desire-path) and What Changes
    (incl. the explicit merchant-recommender anti-pattern).
  - `design.md` — orchestrator-worker + separate verification pass; default single-threaded;
    seeded trust tiers vs. the learned-model "clever trap"; ranking-neutrality; open questions.
  - Spec deltas for 10 capabilities: criteria-extraction, source-classification,
    within-source-skepticism, failure-mode-detection, weighting-ranking, long-tail-coverage,
    orchestration, audit-log, final-advice, provider-configuration.
  - `tasks.md` — implementation order, MVP single-thread before parallel subagents.
- Validated with `openspec validate --strict` (passes).
- Added README, LICENSE (EUPL-1.2), `.gitignore`.

No implementation code yet — proposal awaits approval.

### 2026-06-21 — Resolved open design questions

- Resolved all 6 open questions in `design.md` (Open Questions → Resolved Decisions):
  YAML+regex trust-seed; corroboration threshold ≥2 (configurable); token-based cost
  ceiling (no USD cap in MVP); `plan.json` external memory; advice to Markdown + stdout;
  docs in English.
- Embedded the concrete values into the specs (failure-mode threshold ≥2, token ceiling,
  provider-configuration run-level config keys) and `tasks.md`.
- Re-validated with `openspec validate --strict`.

### 2026-06-21 — MVP implementation (single-threaded)

- Scaffolded the Python package with `uv` (src layout, EUPL-1.2, SPDX headers); pinned
  Python 3.12; added `anthropic`, `pyyaml`, `python-dotenv` and recorded `uv.lock`.
- Implemented the single-threaded orchestrator-worker pipeline:
  - `config.py` — explicit run config (provider/model, token ceiling, parallelism default
    OFF, corroboration threshold ≥2, per-thread bounds, subagent cap); key via env, never logged.
  - `audit.py` — append-only JSONL trail with credential redaction; writes `plan.json` / `advice.md`.
  - `sources.py` + `config/source_tiers.yaml` — seeded, explainable trust-tier classification
    (every tier traces to a rule id; no learned score).
  - `llm.py` — Anthropic Messages-API client: agentic `web_search` loop (model-matched tool
    version, `pause_turn` handling), token accounting + hard ceiling, `output_config.format`
    structured extraction.
  - `criteria.py` / `orchestrator.py` — criteria extraction (disqualifier-first), landscape+plan,
    failure-hunting subagent threads, classification, skepticism/corroboration.
  - `skepticism.py` — independent-corroboration counting + explicit logged rules.
  - `ranking.py` — source-trust × corroboration × failure-severity; no commercial/popularity input.
  - `verify.py` — separate pass dropping ungrounded claims; emits grounding to the trail.
  - `advice.py` + `cli.py` — prescribed advice format; Markdown to run dir + stdout.
- Tests (`tests/test_core.py`): 14 passing — classification, skepticism, ranking neutrality +
  disqualification, audit redaction, config defaults. Ruff clean.
- Remaining: run-wide query dedup (3.4), interactive disqualifier ask-back (4.2), the live
  worked-example run (12.x), and opt-in parallel subagents (13.x).

### 2026-06-21 — Live worked-example validation (Haiku 4.5)

- Made adaptive thinking + `effort` model-aware (`Config.uses_advanced_reasoning`) — both 400
  on Haiku 4.5 / older models; now sent only for the modern Opus/Sonnet/Fable tier.
- Ran the thermos example end-to-end on Haiku 4.5 twice:
  - Run 1 (ceiling 150k): validated the pipeline + the cost-ceiling halt, but a single
    subagent's basic (unfiltered) `web_search` consumed ~187k tokens before others ran, and
    `extract()` saw only prose so findings came back ungrounded and were dropped.
  - Fixes: thread the actually-visited URLs into the extraction prompt and drop any invented
    source_url; lower per-thread defaults to 3 searches / 3 iterations.
  - Run 2 (ceiling 350k): completed normally (~200k tokens), 29 findings, grounded advice in
    the prescribed format.
- Honest finding: of ~50 cited sources only 2 were high-trust; 28 were `unknown`, 20 `low`.
  The disqualification gate (≥2 corroborations in a high-trust source) therefore never fired,
  so "Avoid" was empty despite 13 failure-findings, and recommendations leaned on
  affiliate/manufacturer sources. Next: expand `source_tiers.yaml` (affiliate-review domains,
  manufacturer `/blog` → low), steer subagent search toward high-trust domains, and lower the
  `unknown` ranking weight; a dynamic-filtering-search model (Sonnet/Opus) would help most.
- Marked tasks 12.1 / 12.2 / 12.3 with the caveats above.

### 2026-06-21 — Tier-list tuning + disqualifier-first steering (operator feedback)

- Operator review of run 2 found findings drifting to temperature instead of the taste
  disqualifier, no specialist fora, and a flat trust scheme. Changes:
  - Three-tier evidence hierarchy in `source_tiers.yaml` (high: specialist fora /
    discussion; medium: user-review platforms; low: blogs / affiliate / manufacturer),
    reweighted high 1.0 > medium 0.55 > unknown 0.25 > low 0.1.
  - Disqualifier-first subagent steering: hunt the stated disqualifier specifically, drop
    off-criterion padding, tag each finding's `criterion`, prefer fora/reviews over blogs.
  - Lowered default `effort` to medium after a Sonnet 4.6 run blew a 300k ceiling on a single
    ~500k-token landscape call at effort=high (effort multiplies tokens across ~12 calls/run).
    Note: the token ceiling is a between-call gate, so a single heavy call can overshoot it —
    a true per-call hard cap remains a TODO.
- Re-ran the thermos example on Haiku 4.5 with the tuning (~202k tokens, ~$0.55): source mix
  improved from high 2 / unknown 28 to high 7 / medium 6 / unknown 8; findings now centre on
  the taste disqualifier; the Avoid section correctly disqualified the Klean Kanteen on a
  metallic-taste failure corroborated by 4 users across two high-trust fora. This reproduces
  the spec's worked example (recommend ceramic-coated, reject the offending stainless model).
- Tests: 18 passing; ruff clean.
