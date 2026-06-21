# Crible

> *Crible* (French: "sieve") — a bias-correcting product-research agent.

**Status:** OpenSpec proposal stage. No implementation yet — the design is being specified
first (OpenSpec-first). See [`openspec/changes/add-bias-correcting-research-agent/`](openspec/changes/add-bias-correcting-research-agent/).

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

## License

[EUPL-1.2](LICENSE).

## Support

Open source. A voluntary donation ("buy me a coffee") and attribution/credit are welcome but
are **decoupled from and never influence the ranking**.
