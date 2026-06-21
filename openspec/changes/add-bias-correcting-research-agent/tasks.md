## 1. Project scaffolding (boring, auditable foundation)

- [ ] 1.1 Initialise a Python project managed with `uv` (no direct `pip`); pin Python version
- [ ] 1.2 Add EUPL-1.2 LICENSE and SPDX headers convention; add README with scope + anti-pattern
- [ ] 1.3 Add `.gitignore` (Python, venv, run outputs, secrets) and a `CHANGELOG.md`
- [ ] 1.4 Add the Anthropic SDK dependency via `uv`; record lockfile
- [ ] 1.5 Create config module: provider/model, API-key reference (env/vault), cumulative
      token ceiling, parallelisation switch (default OFF), corroboration threshold (default ≥2),
      per-thread iteration/tool-call bounds, subagent cap
- [ ] 1.6 Add the version-controlled trust-tier seed list (`source_tiers.yaml`) with low/high
      source-type patterns

## 2. Audit trail (build first — everything writes to it)

- [ ] 2.1 Implement an append-only JSONL run-logger (one object per line, type + timestamp)
- [ ] 2.2 Define event types: query, source_visited, classification, skepticism_rule,
      corroboration, score, decision, cost, run_settings
- [ ] 2.3 Add a credential-redaction guard so no key/token can ever be written to the trail
- [ ] 2.4 Add a per-run output directory (audit `.jsonl`, `plan.json`, advice `.md`)

## 3. Provider + tool-use loop (single-threaded)

- [ ] 3.1 Implement the Messages-API client with `web_search` in an agentic tool-use loop
- [ ] 3.2 Enforce per-thread iteration/tool-call bounds with explicit stop conditions
- [ ] 3.3 Enforce the run-level cost/token ceiling; halt and return best-so-far on reach
- [ ] 3.4 Implement query/source deduplication across the run

## 4. Criteria extraction (LEAD)

- [ ] 4.1 Extract positive requirements, disqualifiers, budget and context into a structured set
- [ ] 4.2 Detect a missing-but-likely disqualifier and ask back before proceeding
- [ ] 4.3 Scale extraction depth to question complexity (no heavy loop for trivial questions)
- [ ] 4.4 Log the extracted criteria set to the audit trail

## 5. Landscape, plan + external memory (LEAD)

- [ ] 5.1 Build a broad candidate landscape that deliberately includes long-tail options
- [ ] 5.2 Persist the research plan to `plan.json` (external memory) so it survives long runs
- [ ] 5.3 Record candidate provenance in the audit trail

## 6. Source classification

- [ ] 6.1 Classify each visited source via the seed tier list (allow/deny per type)
- [ ] 6.2 Record source, assigned tier and the matching rule for every source
- [ ] 6.3 Guarantee no learned/black-box score: every tier traces to an explicit rule

## 7. Within-source skepticism + corroboration

- [ ] 7.1 Implement explicit skepticism rules (account age, identical phrasing, praise clusters)
- [ ] 7.2 Count INDEPENDENT corroborations (distinct accounts/sources, varied phrasing, time spread)
- [ ] 7.3 Log every fired rule (name, source/post, triggering signal) to the audit trail

## 8. Failure-mode detection (subagent thread, single-threaded MVP)

- [ ] 8.1 Generate disqualifier-targeted queries per candidate against high-trust sources
- [ ] 8.2 Detect failure modes; record severity and supporting sources
- [ ] 8.3 Distinguish "not found (bounded search)" from "confirmed absent"
- [ ] 8.4 Mark a candidate disqualified when the failure mode clears the corroboration threshold

## 9. Weighting + ranking (LEAD)

- [ ] 9.1 Implement ranking = source-trust × independent-corroboration × failure-severity
- [ ] 9.2 Assert no commercial signal (affiliate/commission/sponsorship) is a ranking input
- [ ] 9.3 Assert no popularity/volume signal is a ranking input (long-tail neutrality)
- [ ] 9.4 Log all three ranking inputs per candidate to the audit trail

## 10. Verification/citation pass (separate step)

- [ ] 10.1 Verify every recommendation/rejection claim has at least one source
- [ ] 10.2 Drop ungrounded claims ("no grounding = no claim")
- [ ] 10.3 Emit the grounding portion of the audit trail as a by-product of this pass

## 11. Final advice output

- [ ] 11.1 Render advice in the prescribed form (best fit + reason + n sources; avoid + failure
      mode + corroboration count + direct links)
- [ ] 11.2 Write advice as Markdown to the run directory and print to stdout
- [ ] 11.3 Assert advice is consistent with the audit trail (every claim traces to the JSONL)

## 12. MVP verification against the worked example

- [ ] 12.1 Run the thermos example end-to-end single-threaded
- [ ] 12.2 Confirm recommended models have no metallic-taste failure mode corroborated in
      independent high-trust sources
- [ ] 12.3 Confirm the audit trail reconstructs the full run

## 13. Parallelisation (only after MVP is verified)

- [ ] 13.1 Add parallel subagent execution behind the default-OFF switch
- [ ] 13.2 Enforce the subagent cap and effort-scales-to-complexity rule under parallel mode
- [ ] 13.3 Record that parallel mode was active in the audit trail
- [ ] 13.4 Re-run the worked example in parallel mode and compare cost/results to single-threaded
