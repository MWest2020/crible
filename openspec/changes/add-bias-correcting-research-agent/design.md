## Context

Crible is a single-user, on-demand product-research agent. The motivation and scope live
in `proposal.md`; this document records the *how* and the technical decisions.

Current state: greenfield. No code exists. The hard constraints from the brief are:

- Backend: Anthropic Messages API + `web_search` tool, in an agentic tool-use loop.
- Model and provider configurable (sovereign/cloud split); keys via config, never hardcoded.
- Python, dependency management with `uv` (never `pip` directly). License EUPL-1.2.
- "Boring and auditable": standard approaches, explicit configuration, ISO-explainable
  choices. Every mechanism must be defensible to an auditor.
- MVP = personal, single-user, a few runs per month. Single-threaded by default;
  parallelisation is an explicit, default-OFF switch.

Stakeholders: the single user (owner/operator) and, after open-source release, external
contributors and auditors who must be able to reconstruct any past run.

## Goals / Non-Goals

**Goals:**
- Correct the marketing/SEO/affiliate bias that a naive LLM amplifies.
- Make every recommendation and every rejection reconstructable from a JSONL audit trail.
- Keep cost predictable and bounded; make the expensive multi-agent mode opt-in.
- Keep all trust and skepticism logic explicit, seeded and logged — no black-box scoring.

**Non-Goals:**
- NOT a merchant-side recommender system (collaborative/content-based/hybrid filtering,
  k-means on descriptions). We never optimise for conversion or revenue.
- NOT a multi-tenant SaaS. No accounts, no public endpoint, no shared key in the MVP.
- NOT a learned trust model. We deliberately refuse a fine-grained-but-unexplainable
  mechanism (the "clever trap").
- NOT real-time or low-latency. A run may take minutes and cost real tokens; that is fine.

## Decisions

### D1 — Orchestrator-worker with a separate verification pass (not single-shot)

A LEAD agent extracts criteria, builds the candidate landscape and a plan, dispatches
subagents (each with its own context exploring one independent thread), then weighs and
ranks. A SEPARATE verification/citation pass checks that every claim has a source and
emits the audit trail as a by-product.

*Why over single-shot:* a single prompt cannot both cast a wide net and stay sceptical;
separating exploration from verification is what lets us catch ungrounded claims.
*Alternative considered:* one large prompt with web_search — rejected: no isolation
between threads, no natural place to enforce grounding, audit trail becomes a reconstruction
guess rather than a record.

### D2 — Single-threaded by default; parallelisation behind an explicit switch

The orchestrator-worker architecture *can* drive parallel subagents, but
`parallelism.enabled` defaults to `false`. Default runs execute subagent threads
sequentially.

*Why:* multi-agent ≈ 15× tokens vs a chat. For a few personal runs/month, sequential is
cheap and predictable, and it removes the risk that the expensive mode fires unattended on
the owner's key. *Alternative:* parallel-by-default with a cap — rejected for the MVP on
cost-sovereignty grounds; the cap stays as a guardrail for when the switch is turned on.

### D3 — Seeded trust tiers + per-run within-source skepticism, NOT a learned score

Source trust is a static, version-controlled seed list (allow/deny per source *type*:
low = manufacturer, webshop, affiliate-blog, top-10-list, sponsored/SEO; high =
topic-specific specialist forums/communities, lived experience, repeated independent
reports). On top of that, per-run signal-based skepticism is applied *within* a source.

*Why over a learned model:* this is the central "clever trap". A learned trust score is
fine-grained but unexplainable — it cannot be defended to an auditor and can silently
re-introduce the very bias we fight. A seeded tier list + explicit, logged rules is boring,
auditable and ISO-explainable. *Trade-off accepted:* the seed list needs manual
maintenance and will be imperfect; we accept that in exchange for explainability.

### D4 — Independent-corroboration counting as the unit of evidence

A claim's weight comes from the number of *independent* corroborations, not from
enthusiasm or volume. One glowing post is not evidence. Independence heuristics
(distinct accounts, distinct sources, non-identical phrasing, spread over time) are
explicit and logged. *Alternative:* sentiment scoring — rejected: that is exactly the
marketing-sentiment signal the tool must ignore.

### D5 — Ranking formula: source-trust × independent-corroboration × failure-severity

Ranking is a transparent function of three logged inputs. It is NEVER influenced by
commercial incentive — no affiliate links, no commission weighting, no sponsored
placement — as a hard design principle independent of whatever (donation-based) business
model is chosen. *Why explicit formula over an LLM "just rank these":* the formula's
inputs are all in the audit trail, so the order is reproducible and explainable.

### D6 — Disqualifier-first, failure-mode-hunting flow

Criteria extraction surfaces NEGATIVE requirements first and asks back when a disqualifier
is absent. Subagents actively hunt failure modes of each candidate in high-trust sources.
*Why:* mainstream rankings ignore disqualifiers because products score fine on other axes;
the disqualifier is usually the whole point of the question (see the thermos example).

### D7 — JSONL audit trail as the system of record

Each run appends structured JSONL events: queries issued, sources visited + classification,
skepticism rules applied, corroboration counts, scores, and the final decision. The
verification pass (D1) produces it as a by-product, so the record cannot drift from the
decision. *Why JSONL:* append-only, line-addressable, diffable, trivially parseable —
boring and auditable.

### D8 — Provider/model configuration and secret handling

Model and provider are config keys (sovereign/cloud split). API keys are read from
environment variables or a vault reference at runtime — never hardcoded, never logged into
the audit trail. *Why:* sovereignty/cost choices change; secrets in source or logs are an
audit failure.

### D9 — Bounded everything (anti-runaway)

Per-thread iteration and tool-call caps with explicit stop conditions; a subagent cap that
scales effort to question complexity; query/source dedup; and a configurable run-level
token/cost ceiling that halts the run when reached. *Why:* the documented orchestration
failure modes (over-spawning, endless loops, redundant queries, runaway cost) must be
designed against, not patched later.

## Risks / Trade-offs

- [Seed tier list is imperfect / goes stale] → Version-control it, make it config, log the
  tier used per source so misclassifications are visible and fixable.
- [Within-source skepticism heuristics produce false positives/negatives] → Keep each rule
  explicit and logged; surface which rules fired so the user can judge; never make a rule a
  hidden black box.
- [High-trust forums are themselves manipulated (astroturfing/shilling)] → Require
  independent corroboration (D4); a single source can never carry a claim alone.
- [Cost runaway when parallelisation is enabled] → Hard cost ceiling (D9) + default-off
  switch (D2); log token spend in the audit trail.
- [LLM fabricates a citation] → Separate verification pass (D1, D7) drops any claim whose
  source cannot be confirmed; "no grounding = no claim".
- [web_search returns biased/affiliate-heavy results] → Classification (D3) down-weights
  low-trust source types regardless of search ranking; long-tail coverage prevents
  popularity from dominating.
- [Mission drift toward a revenue-optimising recommender] → The anti-pattern is written
  into the proposal and the ranking-neutrality requirement; any commercial coupling to
  ranking is a spec violation, not a tuning choice.

## Migration Plan

Greenfield — no migration. Rollout is local install only:
1. Implement MVP single-threaded path (see `tasks.md`).
2. Run against the thermos worked-example; verify the audit trail reconstructs the run.
3. Only after the single-threaded path is verified, enable the parallelisation switch.

Rollback: delete the local checkout; there is no deployed service and no shared state.

## Resolved Decisions

The open questions from the brief were resolved with the operator on 2026-06-21. The chosen
options are now binding design decisions:

- **OQ1 — Trust-tier seed format** → **YAML with domain + regex patterns.** A single
  version-controlled `source_tiers.yaml` maps source-type patterns to a tier. Boring,
  readable, diffable, editable without code changes. (See D3.)
- **OQ2 — Independent-corroboration threshold** → **≥ 2 independent corroborations,
  configurable.** A claim or disqualifying failure mode may affect ranking only when
  corroborated by at least 2 independent sources; the value is a config key. One post is
  never evidence. (See D4.)
- **OQ3 — Cost ceiling** → **conservative cumulative token cap, configurable.** The run
  halts on the token cap and returns best-so-far. Provider-independent; no maintained price
  table needed. A USD cap is explicitly NOT implemented in the MVP. (See D9.)
- **OQ4 — LEAD plan persistence** → **yes, `plan.json` per run** alongside the JSONL audit
  trail in the run directory, so the plan survives long runs. (See D1/D7.)
- **OQ5 — Output channel** → **Markdown file + stdout.** The advice is written as
  `advice.md` in the run directory and also printed to stdout.
- **OQ6 — Spec/doc language** → **English**, for open-source portability and the widest
  contributor reach.

No open questions remain. The change is ready for implementation approval.
