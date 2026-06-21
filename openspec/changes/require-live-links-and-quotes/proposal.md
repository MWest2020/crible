## Why

Operator review of a live advice run found two defects that make the output untrustworthy —
both "experiment-failing":

1. **Broken links.** The advice cited URLs that do not resolve. A dead citation is worse than
   no citation: it destroys trust and is a literal no-go for the app.
2. **No lived-experience quotes.** Findings asserted claims ("no metallic taste reported")
   with only a link — no verbatim excerpt of the actual review/forum post. The user must be
   able to *see* the lived experience, not take an assertion on faith.

Both are quality bugs in already-shipped capabilities (`final-advice`, the verification pass,
`audit-log`), fixed directly given the urgency; this change records the new requirements.

## What Changes

- **Live-link grounding.** Before a source is cited, its URL is probed for liveness. Dead
  links (404/410/unreachable) are dropped; a finding that loses all its sources is dropped
  ("no LIVE grounding = no claim"). Access-restricted-but-real responses (401/403/429) are
  kept — the page exists. Link checking is configurable (`verify_links`, default on) and every
  dropped link is logged.
- **Verbatim quotes.** Every finding MUST carry a short verbatim excerpt (the user's own
  words) from a cited source, surfaced under the claim in the advice. A finding that cannot
  quote a real source is dropped.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `final-advice`: every recommendation/rejection shows a verbatim lived-experience quote
  alongside its (now live) source link.
- `audit-log`: dropped dead links and the link-check outcome are recorded, keeping the run
  reconstructable.

## Impact

- **Code** (implemented this change): `links.py` (new `LinkChecker`), `config.py`
  (`verify_links`, `link_check_timeout` + env), `orchestrator.py` (drop dead links + capture
  quote in extraction), `models.py` (`Finding.quote`), `advice.py` (render quote), `httpx`
  added as a direct dependency via `uv`.
- **Cost/latency**: adds bounded HTTP HEAD/GET probes (cached per run); no extra LLM tokens.
- **Conventions**: uv only; EUPL-1.2 SPDX header on `links.py`; no learned scoring; fully
  auditable.
