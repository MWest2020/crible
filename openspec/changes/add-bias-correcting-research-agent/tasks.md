## 1. Project scaffolding (boring, auditable foundation)

- [x] 1.1 Initialise a Python project managed with `uv` (no direct `pip`); pin Python version
- [x] 1.2 Add EUPL-1.2 LICENSE and SPDX headers convention; add README with scope + anti-pattern
- [x] 1.3 Add `.gitignore` (Python, venv, run outputs, secrets) and a `CHANGELOG.md`
- [x] 1.4 Add the Anthropic SDK dependency via `uv`; record lockfile
- [x] 1.5 Create config module: provider/model, API-key reference (env/vault), cumulative
      token ceiling, parallelisation switch (default OFF), corroboration threshold (default ≥2),
      per-thread iteration/tool-call bounds, subagent cap
- [x] 1.6 Add the version-controlled trust-tier seed list (`source_tiers.yaml`) with low/high
      source-type patterns

## 2. Audit trail (build first — everything writes to it)

- [x] 2.1 Implement an append-only JSONL run-logger (one object per line, type + timestamp)
- [x] 2.2 Define event types: query, source_visited, classification, skepticism_rule,
      corroboration, score, decision, cost, run_settings
- [x] 2.3 Add a credential-redaction guard so no key/token can ever be written to the trail
- [x] 2.4 Add a per-run output directory (audit `.jsonl`, `plan.json`, advice `.md`)

## 3. Provider + tool-use loop (single-threaded)

- [x] 3.1 Implement the Messages-API client with `web_search` in an agentic tool-use loop
- [x] 3.2 Enforce per-thread iteration/tool-call bounds with explicit stop conditions
- [x] 3.3 Enforce the run-level cost/token ceiling; halt and return best-so-far on reach
- [ ] 3.4 Implement query/source deduplication across the run (sources deduped per finding;
      run-wide query dedup still TODO)

## 4. Criteria extraction (LEAD)

- [x] 4.1 Extract positive requirements, disqualifiers, budget and context into a structured set
- [ ] 4.2 Detect a missing-but-likely disqualifier and ask back before proceeding (detected +
      logged today; the non-interactive CLI proceeds — interactive ask-back is TODO)
- [x] 4.3 Scale extraction depth to question complexity (no heavy loop for trivial questions)
- [x] 4.4 Log the extracted criteria set to the audit trail

## 5. Landscape, plan + external memory (LEAD)

- [x] 5.1 Build a broad candidate landscape that deliberately includes long-tail options
- [x] 5.2 Persist the research plan to `plan.json` (external memory) so it survives long runs
- [x] 5.3 Record candidate provenance in the audit trail

## 6. Source classification

- [x] 6.1 Classify each visited source via the seed tier list (allow/deny per type)
- [x] 6.2 Record source, assigned tier and the matching rule for every source
- [x] 6.3 Guarantee no learned/black-box score: every tier traces to an explicit rule

## 7. Within-source skepticism + corroboration

- [x] 7.1 Implement explicit skepticism rules (single-source, below-threshold, no-high-trust;
      account-age / identical-phrasing / praise-cluster signals prompted + logged as flags)
- [x] 7.2 Count INDEPENDENT corroborations (distinct accounts/sources, varied phrasing, time spread)
- [x] 7.3 Log every fired rule (name, source/post, triggering signal) to the audit trail

## 8. Failure-mode detection (subagent thread, single-threaded MVP)

- [x] 8.1 Generate disqualifier-targeted queries per candidate against high-trust sources
- [x] 8.2 Detect failure modes; record severity and supporting sources
- [x] 8.3 Distinguish "not found (bounded search)" from "confirmed absent"
- [x] 8.4 Mark a candidate disqualified when the failure mode clears the corroboration threshold

## 9. Weighting + ranking (LEAD)

- [x] 9.1 Implement ranking = source-trust × independent-corroboration × failure-severity
- [x] 9.2 Assert no commercial signal (affiliate/commission/sponsorship) is a ranking input
- [x] 9.3 Assert no popularity/volume signal is a ranking input (long-tail neutrality)
- [x] 9.4 Log all three ranking inputs per candidate to the audit trail

## 10. Verification/citation pass (separate step)

- [x] 10.1 Verify every recommendation/rejection claim has at least one source
- [x] 10.2 Drop ungrounded claims ("no grounding = no claim")
- [x] 10.3 Emit the grounding portion of the audit trail as a by-product of this pass

## 11. Final advice output

- [x] 11.1 Render advice in the prescribed form (best fit + reason + n sources; avoid + failure
      mode + corroboration count + direct links)
- [x] 11.2 Write advice as Markdown to the run directory and print to stdout
- [x] 11.3 Assert advice is consistent with the audit trail (every claim traces to the JSONL)

## 12. MVP verification against the worked example

- [ ] 12.1 Run the thermos example end-to-end single-threaded (needs a live API key + token spend)
- [ ] 12.2 Confirm recommended models have no metallic-taste failure mode corroborated in
      independent high-trust sources
- [ ] 12.3 Confirm the audit trail reconstructs the full run

## 13. Parallelisation (only after MVP is verified)

- [ ] 13.1 Add parallel subagent execution behind the default-OFF switch
- [ ] 13.2 Enforce the subagent cap and effort-scales-to-complexity rule under parallel mode
- [ ] 13.3 Record that parallel mode was active in the audit trail
- [ ] 13.4 Re-run the worked example in parallel mode and compare cost/results to single-threaded
