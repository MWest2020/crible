## Context

Crible is hard-wired to the Anthropic SDK and its server-side `web_search`. `LLMClient`
(`src/crible/llm.py`) builds an Anthropic client and a `web_search_*` server tool; the
orchestrator's research step assumes the search happens server-side and that
`web_search_tool_result` blocks carry the sources. To support local/sovereign models we must
(a) abstract the provider, and (b) provide retrieval that does not depend on Anthropic's
server tool. The rest of the pipeline (classification, skepticism, ranking, evidence-mix
floor, advice) consumes a normalised `Source` list and is provider-agnostic already — so the
blast radius is the provider + retrieval layer only.

## Goals / Non-Goals

**Goals:**
- Run reasoning on a local/sovereign OpenAI-compatible model (Ollama / vLLM / llama.cpp).
- Retrieve via a client-side search backend we control; offer a fully sovereign path
  (local model + self-hosted SearXNG) where no question/reasoning leaves the host.
- Decouple search mode from provider; keep Anthropic + server search as the default.
- Reuse the existing bounds, cost accounting, audit trail and downstream pipeline unchanged.

**Non-Goals:**
- Not a fine-tuning / model-hosting story — Crible calls an endpoint the operator runs.
- Not adding a learned ranker or relevance model (still rule-based, auditable).
- Not parallelism (covered elsewhere); single-threaded stays the default.
- Not guaranteeing parity of result quality across models — local models may be weaker; that
  is the operator's trade-off, surfaced via the audit trail.

## Decisions

### D1 — Thin provider interface, two implementations

Define a `Provider` with two methods the orchestrator needs: `research(system, prompt, …)`
and `extract(system, prompt, schema)`. Implementations:
- **AnthropicProvider** — today's behaviour; `search_mode=server` uses the server `web_search`
  tool; `search_mode=client` uses the shared client-side tool (D2).
- **OpenAICompatProvider** — uses the `openai` SDK against a configurable `base_url`
  (Ollama `/v1`, vLLM, etc.); always `search_mode=client` (no server tool exists). Structured
  extraction uses the endpoint's JSON / tool-calling support, falling back to instructed-JSON
  parsing when a local model lacks strict structured outputs.
*Why the `openai` SDK:* it is the de-facto standard local endpoints implement; boring and
well-understood. *Alternative:* raw httpx — rejected (re-implements a moving target).

### D2 — Client-side search behind a pluggable backend

A `SearchBackend` interface returns a list of `{url, title, snippet}` for a query. Adapters:
- `searxng` — POST/GET to a self-hosted SearXNG JSON endpoint (sovereign; `base_url` config).
- `tavily` / `brave` — cloud search APIs (key via env), useful when no SearXNG is available.
The client-side `web_search` tool calls the configured backend; results normalise to the
existing `Source` shape so classification/skepticism/ranking/floor are untouched. An optional
`web_fetch` (httpx GET + readability/text extract) lets the model pull a page's content when a
snippet is not enough; bounded by the per-thread tool-call cap.
*Why pluggable:* sovereignty needs self-hosted; convenience needs a zero-infra option. The
choice is explicit config, logged per run.

### D3 — `search_mode` decoupled from provider

Config `search_mode = server | client`. `server` requires the Anthropic provider. `client`
works with any provider and any backend. This lets us (a) keep today's Anthropic+server path
as default, (b) run Anthropic with client search for apples-to-apples backend comparison, and
(c) run local models (always client). The effective combination is recorded in `run_settings`.

### D4 — Bounded manual tool-use loop for client mode

For client search, run a manual function-calling loop: present `web_search`/`web_fetch` tool
schemas, execute the model's tool calls against the backend, feed results back, repeat until
the model stops or the per-thread iteration/tool-call bound is hit. Token/cost accounting
reuses the provider's usage numbers where available; for endpoints without usage, fall back to
`count_tokens`-style estimation and still honour the run ceiling. Dedup queries/sources within
the run (existing concern).

### D5 — Sovereignty is a documented, logged property, not a mode flag

"Sovereign" is simply the combination `provider=openai-compat (local base_url) +
search_mode=client + backend=searxng (local)`. The run records provider, model, base_url
host, search mode and backend so an auditor can see whether any third-party LLM egress
occurred. We do not claim sovereignty beyond what the configuration proves.

## Risks / Trade-offs

- [Local models give weaker structured output] → Provider negotiates JSON/tool-calling and
  falls back to instructed-JSON parsing; failures are logged, not silently dropped.
- [SearXNG/cloud backend down or rate-limited] → Bounded retries + a logged error; the
  evidence-mix floor already turns thin retrieval into an honest caveat rather than a bad pick.
- [Client fetch pulls huge pages] → Cap fetched content size (config); strip to text.
- [New dependency surface (`openai`)] → Optional; only needed for the OpenAI-compat provider;
  installed via `uv`, lockfile-pinned, respecting the project's supply-chain rules.
- [Result-quality gap vs Anthropic] → Out of scope to fix; surfaced via audit so the operator
  judges the sovereignty/quality trade-off.

## Migration Plan

Additive and default-off: the default stays `provider=anthropic, search_mode=server`, so
existing runs are unchanged. Implementation order (apply change): provider interface +
Anthropic adapter refactor (no behaviour change) → client-side search tool + SearXNG backend →
OpenAI-compat provider → manual tool-use loop → audit/config/CLI → docs/tests. Rollback =
revert; the Anthropic path is untouched.

## Open Questions

Proposed defaults marked; to confirm at apply time.

- **OQ1 — default client search backend**: `searxng` (sovereign, needs a URL) vs a zero-infra
  cloud default. *Proposed: no default backend — require explicit `CRIBLE_SEARCH_BACKEND`
  when `search_mode=client`, and document SearXNG as the sovereign choice.*
- **OQ2 — `web_fetch` in the MVP**: include client-side fetch, or snippets-only first?
  *Proposed: snippets-only in the first apply; add `web_fetch` as a fast-follow.*
- **OQ3 — structured output on local models**: require tool-calling/JSON support, or always
  parse instructed-JSON? *Proposed: prefer the endpoint's JSON mode, fall back to
  instructed-JSON parsing; log which path was used.*
- **OQ4 — OpenAI-compat auth**: many local endpoints need no key. *Proposed: `api_key`
  optional for the openai-compat provider; `base_url` required.*
- **OQ5 — backend result count / fetch size caps**: *Proposed: configurable, with conservative
  defaults (e.g. 5 results/query, fetched-page cap ~20k tokens).*
