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
