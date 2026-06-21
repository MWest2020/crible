## Why

Crible's value is trustworthy, auditable verdicts. Two recent fixes got us closer — citations
must now be **live** (dead links dropped) and every finding must carry a **verbatim quote** —
but a gap remains that is make-or-break for success: **nothing confirms the quote is actually
on the page.** The quote is *instructed*-verbatim (the model is told to copy real text), and
the link is merely *reachable*; a model can still attach a plausible quote to a real-but-wrong
URL, or lightly paraphrase. For a bias-correcting tool, "trust me, a user said this" with an
unverifiable quote is exactly the failure mode we exist to kill.

The durable fix is to **ground evidence in fetched page content**: retrieve the cited page,
take the quote from that real text, and verify the quote is present on the page. Evidence that
cannot be grounded is dropped. This also subsumes link-liveness (a page that won't fetch is
dead) and turns "no grounding = no claim" into something literal and checkable.

## What Changes

- **Bounded content fetch.** For credible-tier (high/medium) cited sources, fetch the page
  (server-side `web_fetch` on providers that support it; client-side httpx + text extraction
  otherwise — tying into the provider abstraction in `support-local-sovereign-models`). Bounded
  by a configurable max pages-per-finding and max content size; cached per run; single-threaded
  by default.
- **Quote verification.** Extract the finding's quote from the fetched text, and verify it
  appears on the page (normalised substring / high-similarity match). A finding whose quote
  cannot be located on any of its live cited pages is dropped — verified grounding, or no claim.
- **Link-liveness subsumed.** A source that fails to fetch is treated as dead (replacing the
  separate HEAD probe for fetched sources; the HEAD checker remains for any source not fetched).
- **Audit + config.** Record fetched pages, quote-match results (matched / not-found, score),
  and every drop. All new behaviour configurable via `CRIBLE_*` + CLI with documented defaults;
  fetch can be disabled to fall back to today's link-liveness + instructed-quote behaviour.

## Capabilities

### New Capabilities

- `content-grounded-evidence`: fetch cited credible pages, extract and VERIFY the quote against
  the fetched text, and drop findings whose quote cannot be grounded.

### Modified Capabilities

- `final-advice`: quotes shown are verified present on the live page, not merely instructed.
- `orchestration`: a bounded fetch step feeds real page text into finding extraction and
  verification; reuses the existing per-thread bounds and cost accounting.

## Impact

- **Code** (deferred to apply): a fetch layer (`web_fetch` server tool where available, else
  httpx GET + readability/text extraction), quote-matching util, changes to
  `orchestrator.py`/`verify.py`, `config.py`/`cli.py` knobs, and new audit events.
- **Composition**: builds on `require-live-links-and-quotes` (live links + quote field) and
  dovetails with `support-local-sovereign-models` (client vs server fetch via the provider
  abstraction). On Anthropic, prefer the server `web_fetch_20260209`; on local, client httpx.
- **Cost/latency**: bounded HTTP fetches (cached), capped content size; no new LLM tokens
  beyond feeding fetched text to the existing extraction call (counted against the ceiling).
- **Conventions**: uv only; EUPL-1.2 SPDX headers on new files; no learned scoring; fully
  auditable; single-threaded default.
