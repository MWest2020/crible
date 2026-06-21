# Crible — project conventions

Crible is a single-user, on-demand product-research agent that actively CORRECTS the
marketing/SEO/affiliate bias a naive LLM amplifies, and produces an auditable,
source-backed recommendation. It is NOT a merchant-side recommender system.

## Tech stack

- **Language**: Python.
- **Dependency management**: `uv` only — never `pip` directly.
- **Backend**: Anthropic Messages API with the `web_search` tool, in an agentic
  tool-use loop. Model and provider are configurable (sovereign/cloud split).
- **Secrets**: API keys via environment variables or a vault reference — never hardcoded,
  never logged.
- **License**: EUPL-1.2 (SPDX headers on source files).

## Conventions

- **OpenSpec-first**: no implementation before a change proposal is approved.
- **Boring and auditable**: standard, well-understood approaches; explicit configuration;
  ISO-explainable choices. No learned black-box scoring (the "clever trap").
- **Audit trail**: every run writes an append-only JSONL trail sufficient to reconstruct it.
- **Ranking neutrality (hard principle)**: ranking is never influenced by commercial
  incentive — no affiliate links, no commission weighting, no sponsored placement.
- **Default-cheap**: single-threaded by default; parallelisation is an explicit, default-OFF
  config switch (multi-agent ≈ 15× tokens).
- **Changelog**: maintain `CHANGELOG.md` every session with dated entries.
- **Docs in sync**: README and docs are updated in the same change as the code.

## Distribution

Open source. An optional voluntary donation ("buy me a coffee") and attribution/credit may
exist but are decoupled from and never influence the ranking.
