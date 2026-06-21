## Why

Finding the best product for a specific need has become hostile to the user. Before
reaching an actual product, a person is funneled through blogs, ads, affiliate content,
SEO content-farms, fake reviews, and a flood of products that "work on paper". This is a
documented mass behaviour: people append "reddit" to their search query because they
distrust affiliate systems, SEO content and manufactured reviews and want lived
experience instead. The desire path is real; the tooling to walk it is not.

A naive LLM makes this worse, not better. An LLM retrieves probabilistically and returns
what the *texts* say is best. Because marketing, SEO and affiliate content is positive
and over-represented in those texts, a naive LLM systematically recommends exactly the
products that fail in practice. **Crible exists to actively CORRECT that bias, not amplify
it** — a single-user, on-demand research agent that distils the truth from lived
experience and produces an auditable, source-backed recommendation.

## What Changes

- **NEW**: An orchestrator-worker research agent (LEAD agent + bounded subagents +
  a separate verification pass) built on the Anthropic Messages API with the
  `web_search` tool in an agentic tool-use loop. Model and provider are configurable
  (sovereign/cloud split); keys come from explicit config, never hardcoded.
- **NEW**: Provenance-led source trust classification. Every visited source is classified
  into an explainable, seeded trust tier (low: manufacturer/webshop/affiliate-blog/
  top-10-lists/sponsored-SEO; high: topic-specific specialist forums and communities,
  lived experience, repeated independent reports). No learned, unexplainable scoring
  model — that is the explicit "clever trap" we refuse.
- **NEW**: Within-source skepticism. No source is trusted blindly, forums included
  (parasite-SEO, bought upvotes/karma, astroturfing/shilling, AI-generated reviews).
  Independent corroborations are counted; signals (account age, repeated identical
  phrasing, sudden praise/complaint clusters) are weighed; every skepticism rule applied
  is explicit and logged.
- **NEW**: Disqualifier-first criteria extraction. The agent derives NEGATIVE requirements
  ("no metallic taste") as well as positive ones, budget and context, and asks back when a
  disqualifier is missing. Effort scales to question complexity.
- **NEW**: Active failure-mode detection — the agent hunts for the ways candidates fail in
  high-trust sources, not only for positive matches.
- **NEW**: Ranking by `source-trust × independent-corroboration × failure-mode-severity`,
  never by marketing sentiment, and — as a hard design principle independent of any
  business model — never influenced by commercial incentive (no affiliate links, no
  commission-weighted order, no sponsored placement).
- **NEW**: Long-tail coverage — popularity is not rewarded; a niche product that avoids
  the disqualifier can win.
- **NEW**: Orchestration guardrails against the known failure modes: over-spawning
  (subagent cap + effort-scales-to-complexity), endless loops (bounded iterations/
  tool-calls per thread with explicit stop conditions), redundant queries (query/source
  dedup), and cost (explicit, configurable token/cost ceiling; multi-agent ≈ 15× tokens).
  Parallel subagents are supported but **parallelisation is OFF by default**; it is an
  explicit config switch.
- **NEW**: A fully reconstructable JSONL audit trail per run (queries, visited sources,
  classifications, skepticism rules applied, corroboration counts, scores, final decision).
- **NEW**: A final-advice format where every recommendation AND every rejection carries
  source references, a corroboration count and a reason. No grounding = no claim.
- **EXPLICIT ANTI-PATTERN**: Crible is emphatically NOT a merchant-side recommender
  system (collaborative / content-based / hybrid filtering, k-means on product
  descriptions). Those optimise for conversion/revenue and match on textual and
  behavioural surface signals — precisely the bias we fight.

## Capabilities

### New Capabilities

- `criteria-extraction`: Derive positive requirements, disqualifiers, budget and context
  from the user's question; ask back on missing disqualifiers; scale effort to complexity.
- `source-classification`: Seeded, explainable trust-tier classification of every source
  (allow/deny per source type), no learned black-box score.
- `within-source-skepticism`: Per-run, signal-based skepticism applied inside even
  high-trust sources; independent corroboration counting; explicit, logged rules.
- `failure-mode-detection`: Active search for candidate failure modes in high-trust
  sources, with severity assessment.
- `weighting-ranking`: Ranking by source-trust × corroboration × failure-severity, with a
  hard constraint of commercial-incentive neutrality.
- `long-tail-coverage`: Anti-popularity-bias guarantees so niche products can win.
- `orchestration`: Orchestrator-worker flow with subagent caps, iteration/tool-call
  bounds, dedup, the default-off parallelisation switch, and configurable cost ceilings.
- `audit-log`: Per-run JSONL audit trail capturing every decision input and output.
- `final-advice`: The grounded recommendation+rejection output format.
- `provider-configuration`: Configurable model/provider (sovereign/cloud), API keys via
  explicit config never hardcoded, and run-level cost/parallelisation configuration.

### Modified Capabilities

<!-- None. This is a greenfield project; no existing specs to modify. -->

## Impact

- **New codebase** (Python, managed with `uv` — never `pip` directly). License: EUPL-1.2.
  OpenSpec-first; no implementation until this proposal is approved.
- **External dependency**: Anthropic Messages API + `web_search` tool. Network egress to
  the configured model provider and to the open web.
- **Configuration surface**: provider/model selection, API key reference, trust-tier seed
  list, cost/token ceiling, parallelisation toggle, per-thread iteration/tool-call bounds.
- **Outputs**: a human-readable advice document and a machine-readable JSONL audit trail
  per run.
- **Distribution**: open source. An optional voluntary donation ("buy me a coffee") and
  attribution/credit may exist but are decoupled from and never influence the ranking.
