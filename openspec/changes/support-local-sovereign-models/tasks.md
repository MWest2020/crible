## 1. Provider abstraction (no behaviour change)

- [ ] 1.1 Define a `Provider` interface (`research`, `extract`) and move today's Anthropic
      logic into an `AnthropicProvider` behind it
- [ ] 1.2 Route `LLMClient`/orchestrator through the provider; verify the Anthropic+server
      path is byte-for-byte unchanged (existing tests stay green)
- [ ] 1.3 Add config: `provider` (anthropic | openai-compat), `base_url`, `search_mode`
      (server | client), with documented defaults (anthropic + server)

## 2. Pluggable client-side search

- [ ] 2.1 Define a `SearchBackend` interface returning normalised {url, title, snippet}
- [ ] 2.2 Implement the `searxng` backend (self-hosted JSON endpoint; sovereign)
- [ ] 2.3 Implement at least one cloud backend (tavily or brave; key via env)
- [ ] 2.4 Implement the client-side `web_search` tool calling the configured backend; map
      results to the existing `Source` shape
- [ ] 2.5 Audit events: search backend per run, client search calls (query, backend, count)

## 3. OpenAI-compatible provider

- [ ] 3.1 Add the `openai` dependency via `uv` (lockfile-pinned, supply-chain rules)
- [ ] 3.2 Implement `OpenAICompatProvider` (base_url, optional key) for reasoning
- [ ] 3.3 Structured extraction: prefer the endpoint's JSON/tool-calling, fall back to
      instructed-JSON parsing; log which path was used
- [ ] 3.4 Fail fast on missing `base_url`; validate provider/search_mode combinations

## 4. Client-mode agentic loop

- [ ] 4.1 Manual function-calling loop: present tools, execute calls, feed results back,
      bounded by the per-thread iteration/tool-call limits
- [ ] 4.2 Token/cost accounting against the run ceiling (usage or estimated); query/source dedup

## 5. Config, CLI, audit, sovereignty

- [ ] 5.1 CRIBLE_* env vars + CLI flags for provider, base_url, search_mode, backend, caps
- [ ] 5.2 Record provider, model, base_url host, search_mode and backend in `run_settings`
      (no keys); keep credentials out of the trail
- [ ] 5.3 Document the sovereign combination (local provider + client + searxng)

## 6. Tests + docs

- [ ] 6.1 Test: provider/search_mode validation (server requires Anthropic; openai-compat
      requires base_url)
- [ ] 6.2 Test: searxng backend maps results to normalised sources (mocked HTTP)
- [ ] 6.3 Test: client-mode loop respects the iteration bound and the cost ceiling (fake provider)
- [ ] 6.4 Test: no key/endpoint secret is written to the audit trail
- [ ] 6.5 Keep ruff clean; run `uv run pytest`
- [ ] 6.6 README sovereign quick-start + new flags; CHANGELOG dated entry (in the apply change)
