## Why

The brief and `provider-configuration` promise a "sovereign/cloud split" — model and provider
configurable so a run can stay on infrastructure the operator controls. Today that promise is
unmet: Crible runs **only** on the Anthropic API, and its retrieval depends on Anthropic's
**server-side** `web_search` tool, which exists only for Anthropic models. A local model
(Ollama / vLLM / llama.cpp) has no such tool and no internet of its own, so it cannot drive
Crible at all.

We want a run to be able to execute **fully locally / sovereign**: a local OpenAI-compatible
model for reasoning, and a **client-side** search backend we control (e.g. a self-hosted
SearXNG) for retrieval — so that, in sovereign mode, the only egress is the web searches
themselves, never the question or the reasoning to a third-party LLM. This also decouples
"which model" from "how we search", which is healthy regardless of sovereignty.

This change is **roadmap / spec-only**: it defines the capability so the design is agreed
before any implementation.

## What Changes

- **Provider abstraction.** Introduce a small provider interface with two implementations:
  the existing **Anthropic** provider (server-side `web_search`), and an **OpenAI-compatible**
  provider (for Ollama / vLLM / llama.cpp and any OpenAI-compatible endpoint) driven by a
  configurable `base_url`. The provider is selected by config; keys/endpoints come from config,
  never hardcoded.
- **Client-side search tool.** A `web_search` (and optional `web_fetch`) tool executed by
  Crible itself, backed by a **pluggable search backend**: `searxng` (self-hosted, sovereign),
  and cloud options such as `tavily` / `brave` (key via env). Results are normalised to the
  same `Source` shape (url/title/snippet) the pipeline already consumes, so classification,
  skepticism, ranking and the evidence-mix floor work unchanged.
- **Search mode decoupled from provider.** `search_mode = server | client`. `server` is
  Anthropic-only (today's behaviour). `client` works with any provider, including Anthropic.
  Local models therefore use `client` + a backend; sovereign mode = local provider + SearXNG.
- **Agentic loop over client tools.** For the OpenAI-compatible provider, run a bounded manual
  function-calling loop (model emits tool calls → Crible executes search/fetch → feeds results
  back), reusing the existing per-thread iteration/tool-call bounds and token/cost accounting.
- **Audit + config.** Record the provider, model, search mode and search backend per run; log
  client-side search calls and fetches like today's queries/sources. Everything configurable
  via `CRIBLE_*` env vars + CLI flags with documented defaults.

## Capabilities

### New Capabilities

- `pluggable-search`: a client-side search (and optional fetch) tool with a configurable
  backend (sovereign self-hosted or cloud), normalised to the existing source shape.

### Modified Capabilities

- `provider-configuration`: add an OpenAI-compatible provider (local/sovereign models via
  `base_url`) alongside Anthropic; add the `search_mode` selector; keep keys/endpoints in
  explicit config.
- `orchestration`: the research step abstracts over server-side vs client-side search; for
  client mode it runs a bounded manual tool-use loop, reusing the existing bounds and cost
  accounting.

## Impact

- **Code** (deferred to apply): a `providers/` abstraction (Anthropic + OpenAI-compatible),
  a `search/` package (backend interface + searxng/tavily/brave adapters), changes to
  `llm.py`/`orchestrator.py` to route by provider + search mode, `config.py` + `cli.py`
  knobs, and audit events for provider/search-backend/client-tool calls.
- **Dependencies** (via `uv` only): an OpenAI-compatible client (`openai` SDK) and an HTTP
  client for search backends (`httpx`, already transitively present). No backend is required
  unless selected.
- **Sovereignty**: in `provider=openai-compat (local) + search_mode=client + backend=searxng`,
  no question/reasoning leaves the host; only SearXNG's outbound web queries do. Documented.
- **Docs**: README (sovereign quick-start + new flags) and CHANGELOG updated in the apply
  change.
- **Conventions**: uv only; EUPL-1.2 SPDX headers on new files; no learned scoring; fully
  auditable.
