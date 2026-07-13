---
status: draft
last_reviewed: 2026-07-13
---

# Configuration reference

Every run of Crible is driven by one resolved `Config`
(`src/crible/config.py`). Defaults are safe: parallelisation is OFF, a token
ceiling is always set, and the corroboration threshold is `>= 2`. This page is
the reference for those knobs; for a task-oriented walkthrough see the
[README](../../README.md).

Resolution order (later wins): built-in defaults → `CRIBLE_*` environment
variables → explicit CLI flags / keyword overrides.

## Auth & provider

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `auth_mode` | `api_key` | `CRIBLE_AUTH_MODE` | `api_key` (pay-per-token) or `subscription` (Claude OAuth via `ant auth login`). In subscription mode any `ANTHROPIC_API_KEY` in the environment is stripped before the SDK client is built, so a stray paid key can never silently bill a subscription run. |
| `provider` | `anthropic` | `CRIBLE_PROVIDER` | Provider abstraction for the sovereign/cloud split. |
| `model` | `claude-opus-4-8` | `CRIBLE_MODEL` | Model id; also selects the `web_search` tool version. |
| `base_url` | `None` | `CRIBLE_BASE_URL` | Override endpoint for sovereign deployments. |
| `api_key_env` | `ANTHROPIC_API_KEY` | — | Name of the env var holding the key. The key itself is never hardcoded or logged. |
| `effort` | `medium` | `CRIBLE_EFFORT` | `low \| medium \| high \| xhigh \| max`. Multiplies thinking + tool tokens on every call (~12 calls/run). |

The `web_search` tool version is derived from the model: modern
Opus/Sonnet/Fable models use the dynamic-filtering variant
(`web_search_20260209`, which honours `allowed_domains`/`blocked_domains`);
older models fall back to the basic variant (`web_search_20250305`) and run
without adaptive thinking or the effort parameter.

## Cost & safety ceilings

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `token_ceiling` | `200_000` | `CRIBLE_TOKEN_CEILING` | Cumulative tokens; halts the run when reached (a between-call gate, not a per-call cap). Must be positive. |
| `require_specific` | `True` | — | Refuse to run an over-vague question (the specificity gate); `--force` overrides. |

## Orchestration

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `parallelism_enabled` | `False` | `CRIBLE_PARALLEL` | Explicit opt-in only — parallel subagents cost roughly 15× tokens. |
| `max_subagents` | `8` | `CRIBLE_MAX_SUBAGENTS` | Cap on bounded subagent threads. |
| `max_iterations_per_thread` | `3` | — | Bounded tool-use loop per thread. |
| `max_search_uses_per_thread` | `2` | — | `web_search` `max_uses` cap per pass. |

## Retrieval steering & evidence mix

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `domain_steering_enabled` | `True` | `CRIBLE_DOMAIN_STEERING` | Dual-pass allow/block steering toward trusted sources. |
| `evidence_mix_floor` | `2` | `CRIBLE_EVIDENCE_MIX_FLOOR` | Minimum distinct high+medium sources before a clean verdict; blogs never count as corroboration. Must be `>= 1`. |
| `evidence_research_extra_passes` | `1` | `CRIBLE_EVIDENCE_EXTRA_PASSES` | Bounded re-search on a floor breach, hard-capped at 1 (never a loop). |
| `noncrawlable_search_domains` | `["reddit.com"]` | — | Domains Anthropic's `web_search` user agent cannot crawl; kept out of `allowed_domains` (listing them 400s the request). |
| `blocked_search_domains` | see `config.py` | — | Known blog/affiliate/SEO domains blocked at the source in the open pass. |
| `query_templates` | see `config.py` | — | Deterministic, logged augmentation templates that push searches toward lived experience. |

## Client-side discovery

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `discovery_enabled` | `True` | `CRIBLE_DISCOVERY` | Surface URLs the provider's `web_search` misses (e.g. reddit). |
| `discovery_backend` | `duckduckgo` | `CRIBLE_DISCOVERY_BACKEND` | General search backend that surfaces reddit + fora (no API key). |
| `max_discovery_results` | `6` | — | Cap on discovered URLs fed into the fetch + quote-verify pipeline. |

## Link liveness & content grounding

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `verify_links` | `True` | `CRIBLE_VERIFY_LINKS` | A cited source must resolve or it is dropped; 403/429 count as live, only 404/410/unreachable are dead. |
| `link_check_timeout` | `6.0` | `CRIBLE_LINK_TIMEOUT` | Seconds. |
| `fetch_enabled` | `True` | `CRIBLE_FETCH` | Fetch the cited page from your host and verify the quote is actually on it; subsumes link-liveness when enabled. |
| `max_fetch_pages_per_finding` | `4` | — | Pages per candidate — fewer, but read fully. |
| `max_fetch_chars` | `30_000` | — | Cap on stored page text used for verification. |
| `fetch_prompt_chars` | `12_000` | — | Per-page text fed to the model. |
| `quote_match_ratio` | `0.8` | `CRIBLE_QUOTE_MATCH_RATIO` | Fraction of a quote that must match the fetched page text. |

## Skepticism & ranking

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `corroboration_threshold` | `2` | `CRIBLE_CORROBORATION_THRESHOLD` | Minimum independent corroborations. Must be `>= 1`. |

## Paths

| Setting | Default | Env var | Notes |
| --- | --- | --- | --- |
| `source_tiers_path` | `config/source_tiers.yaml` | `CRIBLE_SOURCE_TIERS` | The single, version-controlled source-trust tier list. |
| `runs_dir` | `runs` | `CRIBLE_RUNS_DIR` | Each run writes a directory with `audit.jsonl`, `plan.json`, and `advice.md`. |

Non-secret settings are recorded per run in the audit trail
(`Config.effective_settings()`) for reproducibility; secret values (the API key
and `ANTHROPIC_AUTH_TOKEN`) are redacted from any audit output.
