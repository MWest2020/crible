# Crible

> *Crible* (French: "sieve") — a bias-correcting product-research agent.

**Status:** MVP implemented (single-threaded). The OpenSpec change
[`add-bias-correcting-research-agent`](openspec/changes/add-bias-correcting-research-agent/)
is approved and most of `tasks.md` is done; the live end-to-end worked-example run and the
opt-in parallel mode are the remaining items. The deterministic core (source classification,
skepticism/corroboration, ranking, audit redaction) is covered by tests.

## Install & run

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) (never `pip` directly).

```
uv sync                                   # reproducible install from uv.lock
export ANTHROPIC_API_KEY=...              # never hardcoded, never logged
uv run crible "the best travel thermos for quality coffee, no metallic taste"
```

Each run writes a directory under `runs/` containing `audit.jsonl` (the full trail),
`plan.json` (the LEAD plan), and `advice.md` (the recommendation). Tune behaviour with
`--model`, `--effort`, `--token-ceiling`, `--max-subagents`, `--corroboration-threshold`,
or the matching `CRIBLE_*` environment variables. Parallel subagents are an explicit
opt-in (`CRIBLE_PARALLEL=1`) and default OFF.

### Retrieval steering & evidence-mix floor

To counter blog/affiliate-dominated search results, retrieval is **steered toward trusted
sources** and gated by an **evidence-mix floor**:

- **Domain-steered dual pass.** Each candidate is searched twice — a high-trust pass that
  allow-lists the specialist fora + review platforms named in `config/source_tiers.yaml`,
  and an open pass that blocks known affiliate/blog domains. (`allowed_domains` only covers
  domain-listed sources, so the open pass + query augmentation reach the regex/path fora.)
  Disable with `--no-domain-steering` / `CRIBLE_DOMAIN_STEERING=0`.
- **Forum/review query augmentation.** Deterministic, logged query templates push searches
  toward lived experience (reddit, `site:` fora, "review"/"long-term").
- **Evidence-mix floor.** Blogs never count as corroboration. If a candidate has fewer than
  `--evidence-mix-floor` (default 2; `CRIBLE_EVIDENCE_MIX_FLOOR`) distinct high+medium
  sources, one bounded high-trust re-search runs (`--evidence-extra-passes`, default 1,
  capped at 1; `CRIBLE_EVIDENCE_EXTRA_PASSES`). If still short, the advice carries a loud
  `evidence-mix-floor-not-met` caveat — a clean "Avoid" section always says whether it means
  "nothing failed" or "not enough trustworthy sources to judge".

### Content grounding (live links + verified quotes)

Because Anthropic's `web_search` user-agent cannot crawl some key communities (e.g. reddit),
Crible fetches cited pages **itself** (`httpx` from your host) and **verifies each quote
against the real page text** — a finding whose quote can't be grounded, or whose page won't
fetch, is dropped (no live, grounded quote = no claim). Tune with `--no-fetch` /
`CRIBLE_FETCH=0` and `--quote-match-ratio` / `CRIBLE_QUOTE_MATCH_RATIO` (default 0.8). Query
augmentation also hunts the **topic's own specialist community** (`best <topic> forum`), not
just reddit.

Run the tests with `uv run pytest`.

## What this is

You want the best product for a specific need — for yourself or as a gift. The open web is
hostile to that goal: before you reach a product you are funneled through blogs, ads,
affiliate content, SEO content-farms and fake reviews. People now append "reddit" to their
searches because they trust lived experience over manufactured marketing.

A naive LLM makes this **worse**: it retrieves probabilistically and returns what the *texts*
say is best — and marketing/SEO/affiliate content is positive and over-represented. So a
naive LLM recommends exactly the products that fail in practice.

**Crible actively corrects that bias.** It is a single-user, on-demand research agent that
distils the truth from lived experience and delivers an auditable, source-backed
recommendation — including *why* products were rejected.

## What this is NOT

Crible is emphatically **not** a merchant-side recommender system (collaborative filtering,
content-based filtering, hybrid models, k-means over product descriptions). Those optimise
for conversion/revenue and match on textual/behavioural surface signals — precisely the bias
we fight.

## Core principles

1. **Provenance-led.** Every source is classified into an explainable trust tier
   (low: manufacturer/webshop/affiliate-blog/top-10-list/sponsored-SEO;
   high: topic-specific forums/communities, lived experience, repeated independent reports).
2. **Trust no source blindly** — forums included. Within-source skepticism counts
   *independent* corroborations and flags astroturfing/shilling/AI-reviews with explicit,
   logged rules.
3. **Disqualifiers first.** Hunt the negative requirements ("no metallic taste") and the
   failure modes of candidates, not just positive matches.
4. **Long-tail coverage.** Popularity is not rewarded; a niche product can win.
5. **Auditable.** Every recommendation *and* every rejection carries sources, a corroboration
   count and a reason. No grounding = no claim.
6. **Ranking is never influenced by commercial incentive** — a hard design principle
   independent of any business model.

## Architecture (planned)

Orchestrator-worker, not single-shot: LEAD criteria-extraction → LEAD landscape+plan →
bounded subagents (independent threads) → LEAD weighting+ranking → a **separate**
verification/citation pass → final advice. Single-threaded by default; parallelisation is an
explicit, default-OFF config switch (multi-agent ≈ 15× tokens).

## Tech

Python (managed with `uv`, never `pip` directly). Anthropic Messages API + `web_search` in an
agentic tool-use loop; model/provider configurable (sovereign/cloud split); keys via config,
never hardcoded. Per-run JSONL audit trail.

## Roadmap

- **Local / sovereign models** (planned — see
  [`openspec/changes/support-local-sovereign-models/`](openspec/changes/support-local-sovereign-models/)).
  Today Crible runs only on the Anthropic API with its server-side `web_search`. We want to
  run fully local/sovereign models (Ollama / vLLM, OpenAI-compatible) with a **client-side**
  search backend (e.g. self-hosted SearXNG), so a run can stay entirely on your own
  infrastructure. This needs a provider abstraction plus a pluggable client-side search tool.
- **Verify domain steering on a dynamic-filtering model** — `allowed_domains`/`blocked_domains`
  apply on `web_search_20260209` (Opus/Sonnet); Haiku's basic search rejects them and degrades.
- **Parallel subagents** behind the default-OFF switch (`add-bias-correcting-research-agent`
  tasks 13.x), run-wide query dedup (3.4), and interactive disqualifier ask-back (4.2).
- **A true per-call cost cap** — the token ceiling is currently a between-call gate.

## License

[EUPL-1.2](LICENSE).

## Support

Open source. A voluntary donation ("buy me a coffee") and attribution/credit are welcome but
are **decoupled from and never influence the ranking**.
