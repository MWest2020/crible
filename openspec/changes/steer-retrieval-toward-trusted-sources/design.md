## Context

Crible's deterministic ranker and credible-only corroboration are sound, but retrieval
feeds them blog/affiliate-dominated input. `web_search` currently runs with only `max_uses`
plus a `blocked_domains` list (added in the prior change); `source_tiers.yaml` classifies
sources only *after* retrieval. There is no mechanism to (a) actively pull from trusted
sources during retrieval, or (b) guarantee a minimum of trustworthy evidence before a
verdict. This change adds both, OpenSpec-first.

Current baseline already in code (do not re-spec): corroboration counts credible tiers only
(low excluded); recommendations require credible grounding; the open search pass carries
`blocked_domains`; the subagent prompt nudges toward fora/reviews. What is NOT yet built and
is the subject of this change: the dedicated high-trust allow-list pass, deterministic query
augmentation, and the evidence-mix floor + bounded re-search + loud caveat.

Relationship to existing capabilities: this refines `within-source-skepticism`
(corroboration) and `failure-mode-detection` (search) but is grouped as a new `evidence-mix`
capability for cohesion; steering additions live under `orchestration`, and the domain-list
exposure under `source-classification`.

## Goals / Non-Goals

**Goals:**
- Steer retrieval toward high/medium-trust sources, not just filter after the fact.
- Make evidence sufficiency explicit, configurable, and logged; never a silent pass.
- Keep every steering and floor decision traceable to an explicit rule/config value.
- Reduce wasted blog tokens; stay single-threaded and bounded (one extra pass).

**Non-Goals:**
- No learned/black-box scoring or relevance model.
- No parallelism / token multiplier (the re-search is one bounded pass, not a loop).
- Not changing the ranking formula or the trust tiers themselves (only how they steer
  retrieval and gate evidence sufficiency).

## Decisions

### D1 — Dual-pass search, because `allowed_domains` cannot express the regex/path forum rules

`source_tiers.yaml` has two kinds of high/medium rules: explicit **domain** lists (e.g.
`reddit.com`, `home-barista.com`, `amazon.`) and **regex/path** rules (e.g. any URL with
`/forum/` or `community.`). `web_search`'s `allowed_domains` filters by domain only, so it
can enforce the domain-listed sources but is structurally blind to the regex/path rules.

Decision: run two passes per research step.
- **High-trust pass**: `allowed_domains` = the domain-listed high + medium entries extracted
  from the tier list. Guarantees trusted-source coverage for the listed domains.
- **Open pass**: `blocked_domains` = the known affiliate/blog domains. Catches the
  regex/path fora (and anything else good) that an allow-list cannot name, while keeping the
  worst blogs out.
Query augmentation (D2) compensates for the regex/path gap on the open pass by biasing it
toward fora/reviews. *Alternative considered:* a single allow-list pass — rejected because
it would silently exclude every regex/path forum, which are exactly the long-tail
specialist communities we want.

### D2 — Deterministic query augmentation (templated, logged), not model-discretion

For each subagent search, derive additional queries from explicit templates, e.g.
`"{candidate} {disqualifier} reddit"`, `site:{forum}` for each domain-listed forum,
`"{candidate} long-term review"`. Templates are config; the exact templates applied per
search are logged. *Why deterministic:* it is auditable and reproducible, and it does not
rely on the model remembering to chase lived experience. *Alternative:* leave it to the
prompt (current state) — kept as a fallback but insufficient alone.

### D3 — Evidence-mix floor as config, with one bounded re-search and a loud caveat

- Low-tier sources never count as corroboration (already true) — restated here as the floor
  precondition: only high+medium sources count toward the floor.
- `evidence_mix_floor` (config, default proposed below): the minimum number of distinct
  high+medium sources required to *accept* a finding's corroboration (and, aggregated, to
  judge a candidate).
- On breach: exactly ONE targeted high-trust re-search (the D1 high-trust pass with
  augmented queries), bounded by `evidence_research_extra_passes` (default 1).
- If still below floor: proceed, but set a `evidence-mix-floor-not-met` caveat on the
  finding/candidate; the advice MUST render it. The Avoid section explicitly distinguishes
  "nothing failed (sufficient trusted sources searched)" from "insufficient trusted sources
  to judge". *Why never silent:* a clean Avoid section is otherwise ambiguous and misleading
  — the worst failure mode for a tool whose whole value is trustworthy verdicts.

### D4 — Steering lists come only from `source_tiers.yaml`

The allow/block domain lists are extracted from the existing seed tier list (domain-match
rules), not a new list. One source of truth, fully auditable, no learned component.

## Risks / Trade-offs

- [`allowed_domains` misses regex/path fora] → Mitigated by the open pass + query
  augmentation (D1/D2); documented as a known limitation, not hidden.
- [Targeted re-search adds tokens] → Bounded to one pass and only when the floor is breached;
  net effect is fewer blog tokens. Logged so cost is visible.
- [Floor too strict → many "insufficient evidence" results] → Floor is configurable with a
  conservative default; the caveat is honest rather than forcing a verdict.
- [`web_search_20250305` vs `_20260209` param support] → Both accept
  `allowed_domains`/`blocked_domains`; verify at apply and degrade gracefully (skip steering
  with a logged note if a provider rejects the params) rather than failing the run.
- [Query augmentation overfits to one locale/site] → Templates are config and logged, so
  they can be tuned without code changes.

## Migration Plan

Additive; no data migration. Implementation order is in `tasks.md` (config + audit events
first, then steering, then the floor/re-search/caveat, then docs/tests). Defaults are chosen
so an un-configured run behaves like today plus the high-trust pass; the floor defaults
conservative. Rollback = revert the change; runs still work without steering.

## Resolved Decisions

Confirmed with the operator on 2026-06-21 (binding for apply):

- **OQ1 — `evidence_mix_floor`** → **2** distinct high+medium sources per finding before its
  corroboration is accepted without a caveat (matches the corroboration threshold);
  configurable via `CRIBLE_EVIDENCE_MIX_FLOOR` / `--evidence-mix-floor`.
- **OQ2 — re-search bound** → **1** extra targeted pass, hard-capped at 1
  (`CRIBLE_EVIDENCE_EXTRA_PASSES`); never a loop.
- **OQ3 — floor scope** → **both**: per-finding for corroboration acceptance, per-candidate
  for the advice `evidence-mix-floor-not-met` caveat.
- **OQ4 — pass order** → **high-trust pass first**, then the open pass; each bounded by
  `max_search_uses_per_thread`.
- **OQ5 — query templates** → **yes**, ship a documented default list (reddit desire-path,
  `site:` per listed forum, "review"/"long-term"), editable via config.
- **OQ6 — graceful degradation** → **yes**: if a provider rejects
  `allowed_domains`/`blocked_domains`, skip steering and log a note rather than fail the run.
- **Baseline**: commit `68b3b34` (credible-only corroboration, recommendation gate, open-pass
  blocklist) is **kept as the baseline**; this change specs only the not-yet-built steering,
  floor, re-search and caveat on top of it.

No open questions remain. Ready for `/opsx apply` on the operator's go-ahead.
