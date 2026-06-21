## Context

After `require-live-links-and-quotes`, a finding carries a verbatim quote and only live links
survive. But the quote is produced by the model from what it read during search (snippets /
summarised content), not checked against the page itself, and link-liveness only proves a URL
resolves. The remaining trust gap: a quote may be paraphrased, or attached to a real-but-wrong
URL. This change closes it by fetching the page and verifying the quote against its text.

The downstream pipeline already consumes normalised `Source`s and `Finding`s with a `quote`;
this change adds a fetch+verify step and drops what it cannot ground, so nothing else needs to
change to benefit.

## Goals / Non-Goals

**Goals:**
- Ground each finding's quote in the actual fetched page text; drop unverifiable quotes.
- Subsume link-liveness for fetched sources (a page that won't fetch is dead).
- Stay bounded, single-threaded by default, auditable, and configurable (fetch can be off).
- Work on both Anthropic (server `web_fetch`) and local providers (client httpx), via the
  provider abstraction.

**Non-Goals:**
- Not full-text semantic analysis of pages — only locate/verify the specific quote.
- Not a crawler — fetch only already-cited URLs (as web_fetch requires), bounded.
- No learned matching model — quote verification is explicit normalised string matching.
- Not parallelism; a small IO concurrency for fetches is allowed but not an LLM multiplier.

## Decisions

### D1 — Verify the quote, don't just fetch

Fetch the cited credible page(s), then check the finding's `quote` against the extracted text
with a deterministic match: normalise whitespace/case/quotes, then require either an exact
substring or a high token-overlap ratio above a configurable threshold. Matched → keep and
record the score; not found on any live cited page → drop the finding. *Why a threshold, not
exact-only:* fetched text extraction (HTML→text) introduces minor noise (ellipses, joined
lines); exact-only would over-drop. *Why not a learned matcher:* must stay auditable.

### D2 — Quotes come FROM fetched text, not search snippets

Feed the fetched page text into the extraction step so the model quotes from real content.
This both improves quote fidelity and means the verification (D1) is checking against the same
text the model saw. *Alternative:* keep search-snippet quotes and only verify — rejected:
verification would over-drop because snippets ≠ full page text.

### D3 — Server vs client fetch via the provider abstraction

On Anthropic, prefer the server `web_fetch_20260209` tool (no extra egress from our host). On
local/OpenAI-compatible providers (no server fetch), use client-side httpx GET + text
extraction. This mirrors the search server/client split in `support-local-sovereign-models`
and keeps sovereign runs sovereign. *Note:* `web_fetch` only fetches URLs already present in
the conversation — exactly our cited URLs — so it composes cleanly.

### D4 — Bounded and cached

Fetch only credible-tier (high/medium) sources, at most `max_fetch_pages_per_finding`
(default small), capped at `max_fetch_chars` per page; cache by URL per run. A small IO thread
pool MAY fetch concurrently (this is HTTP IO, not the LLM-subagent multiplier the scope rules
guard against), but single-threaded sequential is the safe default. Failures count as dead.

### D5 — Fetch is optional; degrade to today's behaviour

`fetch_enabled` (default on). With it off, the system falls back to `require-live-links-and-
quotes` behaviour (HEAD liveness + instructed quote). If a provider's server fetch is rejected,
degrade to client httpx (or, if that is disabled, to HEAD liveness) with a logged note —
never fail the run.

## Risks / Trade-offs

- [Over-dropping on extraction noise] → similarity threshold + normalisation (D1); the
  threshold is config and logged so it can be tuned.
- [Fetch latency on many sources] → bounded pages/finding + size cap + cache + optional IO
  concurrency.
- [Paywalled / JS-rendered pages yield poor text] → if a quote can't be verified there, the
  finding drops (conservative, matches the "trust" priority); the evidence-mix floor then
  surfaces resulting thinness as an honest caveat rather than a bad pick.
- [web_fetch availability varies by provider/platform] → server→client→HEAD degradation (D3/D5).

## Migration Plan

Additive, default-on but safely degradable. Order: fetch layer (client httpx + text extract)
→ quote-matching util + verify step (drop unverifiable) → wire server `web_fetch` for Anthropic
→ config/CLI/audit → tests/docs. Rollback: set `fetch_enabled=false` (instant) or revert.

## Open Questions

Proposed defaults marked; confirm at apply.

- **OQ1 — match strictness**: normalised-substring only, or substring OR token-overlap ≥ T?
  *Proposed: substring OR token-overlap ≥ 0.8 (configurable `CRIBLE_QUOTE_MATCH_RATIO`).*
- **OQ2 — fetch caps**: pages per finding and bytes per page. *Proposed: ≤2 pages/finding,
  ≤20k chars/page (configurable).*
- **OQ3 — IO concurrency**: sequential or a small fetch pool? *Proposed: sequential default;
  optional pool of ≤4 behind a flag (IO only, not LLM).*
- **OQ4 — client text extraction**: a dependency (e.g. readability/trafilatura) or a minimal
  built-in HTML→text strip? *Proposed: minimal built-in strip first (no heavy dep); revisit if
  quality demands it.*
- **OQ5 — fetch scope**: credible-tier only, or also unknown-tier leads? *Proposed: credible
  (high+medium) only — unknown/low never become evidence anyway.*
