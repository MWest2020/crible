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
