## ADDED Requirements

### Requirement: Every cited source link must be live

The system SHALL verify that each source URL resolves before citing it, and SHALL drop dead
links (HTTP 404/410 or unreachable: DNS/connection/timeout). Access-restricted responses
(401/403/429) count as live, since the page exists. A finding left with no live source after
this check SHALL be dropped — no live grounding, no claim. Link checking SHALL be configurable
with a documented default of on.

#### Scenario: A dead link is dropped

- **WHEN** a finding cites a URL that returns 404/410 or is unreachable
- **THEN** that source is removed from the finding and the drop is recorded in the audit trail

#### Scenario: A finding with only dead links is dropped

- **WHEN** every source of a finding fails the liveness check
- **THEN** the finding is dropped and does not appear in the advice

#### Scenario: A bot-blocked but real page is kept

- **WHEN** a cited URL returns 401, 403 or 429
- **THEN** the source is kept (the page exists; a human can reach it)

### Requirement: Every finding shows a verbatim lived-experience quote

The system SHALL attach to every finding a short verbatim excerpt (the source author's own
words) from one of its cited sources, and SHALL surface that quote alongside the claim in the
final advice. A finding that cannot quote a real source SHALL be dropped.

#### Scenario: Recommendation shows a quote

- **WHEN** the advice recommends or rejects a product
- **THEN** each supporting/failing claim is shown with a verbatim quote from a cited source
- **AND** the quote appears next to the (live) source link
