## ADDED Requirements

### Requirement: Cited credible pages are fetched

The system SHALL fetch the content of cited credible-tier (high/medium) sources before a
finding is accepted, bounded by configurable per-finding page and content-size caps and cached
per run. Fetching SHALL use the provider's server-side fetch where available and a client-side
fetch otherwise; a source that fails to fetch SHALL be treated as dead.

#### Scenario: Credible cited page is fetched

- **WHEN** a finding cites a high or medium source
- **THEN** the system fetches that page's text (server-side or client-side) within the
  configured caps
- **AND** records the fetch in the audit trail

#### Scenario: Unfetchable source is treated as dead

- **WHEN** a cited page cannot be fetched (error/timeout/not found)
- **THEN** that source is dropped as dead and the drop is recorded

### Requirement: A finding's quote MUST be verified against the fetched page

The system SHALL verify that a finding's quote appears in the fetched text of one of its cited
pages, using an explicit normalised match (exact substring or token-overlap above a
configurable threshold). A finding whose quote cannot be located on any of its live cited pages
SHALL be dropped — verified grounding, or no claim. The match outcome SHALL be recorded.

#### Scenario: Verified quote is kept

- **WHEN** a finding's quote matches the fetched text of a cited page above the threshold
- **THEN** the finding is kept and the match (page, score) is recorded in the audit trail

#### Scenario: Unverifiable quote is dropped

- **WHEN** a finding's quote cannot be found on any of its cited live pages
- **THEN** the finding is dropped and the drop (with reason) is recorded

### Requirement: Content fetching is configurable and degrades safely

Content fetching SHALL be configurable (default on) and SHALL degrade rather than fail: if a
provider's server fetch is rejected, fall back to client fetch, then to link-liveness only,
each with a logged note. With fetching disabled, the system SHALL fall back to link-liveness +
the instructed verbatim quote.

#### Scenario: Provider rejects server fetch

- **WHEN** the configured provider rejects server-side fetch
- **THEN** the system falls back to client-side fetch (or link-liveness if disabled) and logs
  the degradation, without failing the run

#### Scenario: Fetching disabled

- **WHEN** content fetching is turned off
- **THEN** the system uses link-liveness and the instructed quote, as before
