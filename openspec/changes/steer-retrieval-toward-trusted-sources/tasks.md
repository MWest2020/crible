## 1. Config + audit events (foundation, no behaviour change yet)

- [ ] 1.1 Add config knobs (env + CLI, documented defaults): `evidence_mix_floor` (default 2),
      `evidence_research_extra_passes` (default 1, hard-capped at 1), `domain_steering_enabled`
      (default on), `query_templates` (default list)
- [ ] 1.2 Add audit event types: `search_domains` (allowed/blocked per pass),
      `query_templates`, `source_tier_mix` (per finding/candidate), `floor_check`,
      `evidence_mix_floor_not_met`
- [ ] 1.3 Record the effective new settings in the `run_settings` event

## 2. Source-classification: expose steering lists

- [ ] 2.1 Add `TierList.allow_domains()` / `block_domains()` deriving domain-match entries
      (high+medium allow; low block) from the seed list, excluding regex/path rules
- [ ] 2.2 Make each block/allow entry attributable to its seed rule id (for the audit trail)

## 3. Orchestration: domain-steered dual-pass search

- [ ] 3.1 `llm.py`: pass `allowed_domains`/`blocked_domains` to `web_search`; expose a
      high-trust pass (allow-list) and the open pass (block-list)
- [ ] 3.2 Graceful degradation: if the provider rejects the domain params, skip steering and
      log a note instead of failing
- [ ] 3.3 Log `search_domains` (allowed/blocked) for every pass

## 4. Orchestration: deterministic query augmentation

- [ ] 4.1 Build templated queries per subagent search (reddit desire-path, `site:` per listed
      forum, "review"/"long-term") from config
- [ ] 4.2 Log the `query_templates` applied per search

## 5. Evidence-mix: floor, bounded re-search, caveat

- [ ] 5.1 Enforce low-tier-never-corroborates as the floor precondition (already true; assert
      + cover by test)
- [ ] 5.2 Compute the per-finding / per-candidate high+medium source mix; log `source_tier_mix`
- [ ] 5.3 On floor breach, run ONE bounded targeted high-trust re-search (high-trust pass +
      augmented queries); log `floor_check` before/after
- [ ] 5.4 If still below floor, set the `evidence-mix-floor-not-met` caveat and log it

## 6. Advice: surface the caveat + disambiguate

- [ ] 6.1 Render the `evidence-mix-floor-not-met` caveat per affected candidate
- [ ] 6.2 Make the Avoid section explicit: "trusted sources searched, nothing failed" vs
      "insufficient trustworthy sources to judge"

## 7. Tests + docs

- [ ] 7.1 Test: low-tier excluded from corroboration (extend existing coverage)
- [ ] 7.2 Test: floor breach triggers exactly one re-search (bounded, no loop)
- [ ] 7.3 Test: floor-not-met emits the caveat and the advice surfaces it
- [ ] 7.4 Test: domain steering passes the correct allow/block lists (derived from the seed)
- [ ] 7.5 Keep ruff clean; run `uv run pytest`
- [ ] 7.6 Update README (new flags/env vars + behaviour) and CHANGELOG (dated entry) in this
      change
