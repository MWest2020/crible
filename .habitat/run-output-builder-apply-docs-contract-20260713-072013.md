# Habitat builder — apply-docs-contract

_run_id builder-apply-docs-contract-20260713-072013 · verdict ok · 2026-07-13T07:22:38Z_

---

All done. The implementation stays strictly within the change's scope.

## Run report — `apply-docs-contract`

**What I changed (branch `habitat/builder/apply-docs-contract`, not pushed):**

- **`docs/index.md`** (new) — one-paragraph description of Crible, status (MVP, single-threaded), link to the README (which it references, not replaces), and links to the present sections.
- **`docs/reference/configuration.md`** (new) — the one required reference page, sourced from `src/crible/config.py` + README: auth/provider, cost ceilings, orchestration, retrieval steering & evidence mix, client-side discovery, link/fetch grounding, skepticism/ranking, and paths — each knob with its default and `CRIBLE_*` env var.
- **`openspec/changes/apply-docs-contract/tasks.md`** — tasks 1.1–3.1 checked off with notes.

**Decisions:**
- Repo had **no `docs/`** and **no loose docs** (only `README.md`/`CHANGELOG.md` at root, which stay per contract). So this is the **minimum-viable** case: `index.md` + one reference page. **No stubs** were needed (nothing was moved).
- **`.mcp.json` was already present in root and matches the seed template exactly** (`handbook`, `type: http`, `url: TODO-change-3`) — left unchanged rather than rewritten identically.
- Front matter on every page: `status: draft` + `last_reviewed: 2026-07-13` (migration date, no content review), **no `owner` field**. Language: English throughout.

**Self-check (task 3.1) — passed:** only `reference/` carries markdown (plus root `index.md`), every page has front matter, one language (English), no `owner` field.

**Task 4.1 (open PR) — left to the harness/Mark, not done by me.** Task 1.1 states the habitat harness manages branches and pushes, and my role never merges/pushes. The branch is unpushed and uncommitted; I'm handing off the commit/push/PR step. PR material ready to use:

- **Title:** `docs: apply handbook docs contract`
- **Body (contract points applied):**
  - [x] `docs/` structure per contract (`index.md` + `reference/`; empty dirs omitted)
  - [x] Minimum viable for a repo with no prior docs (`index.md` + one reference page)
  - [x] Front matter on every page (`status`/`last_reviewed`); migrated-without-review → `status: draft`, `last_reviewed: 2026-07-13`; **no `owner`**
  - [x] `index.md` references the README (does not replace it)
  - [x] One language per repo: English
  - [x] `.mcp.json` present per template; placeholder `TODO-change-3` retained
  - [x] No changes outside scope; no `CLAUDE.md` / `.claude/agents/` / CI edits; no merge

**Stopping here** as instructed — Mark merges.
