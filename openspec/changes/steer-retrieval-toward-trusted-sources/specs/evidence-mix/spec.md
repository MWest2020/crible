## ADDED Requirements

### Requirement: Low-trust sources never count as corroboration

The system SHALL NOT count low-trust (blog / affiliate / marketing) or unclassified sources
toward a finding's corroboration. Such sources MAY provide leads to follow but MUST NEVER be
counted as evidence — ten echo-chamber blogs are not corroboration.

#### Scenario: A finding backed only by blogs has zero corroboration

- **WHEN** a finding's only sources are low-trust or unknown
- **THEN** its corroboration count is 0
- **AND** a `no-credible-source` rule is recorded in the audit trail

#### Scenario: Only high and medium sources count toward corroboration

- **WHEN** a finding cites a mix of high, medium and low sources
- **THEN** only the high and medium sources contribute to the corroboration count
- **AND** the low sources are recorded as leads, not evidence

### Requirement: Configurable evidence-mix floor

The system SHALL enforce a configurable minimum number of distinct high+medium sources
("evidence-mix floor") before a finding's corroboration is accepted without a caveat. The
floor SHALL be configuration (env var + CLI flag) with a documented default, not a hardcoded
magic number.

#### Scenario: Finding meets the floor

- **WHEN** a finding has at least `evidence_mix_floor` distinct high+medium sources
- **THEN** its corroboration is accepted and a `floor-met` check is recorded
- **AND** the per-finding source-tier mix is recorded in the audit trail

#### Scenario: Floor value is configurable

- **WHEN** the operator sets the evidence-mix floor via configuration
- **THEN** the run enforces that floor
- **AND** the effective floor value is recorded in the audit trail

### Requirement: Floor breach triggers one bounded targeted high-trust re-search

The system SHALL, when a finding/candidate falls below the evidence-mix floor, perform
exactly ONE bounded targeted high-trust re-search (the high-trust pass with augmented
queries). The number of extra passes SHALL be configurable and bounded — it MUST NOT loop.

#### Scenario: Under-evidenced finding triggers a single re-search

- **WHEN** a finding is below the evidence-mix floor after the initial search
- **THEN** the system performs one targeted high-trust re-search
- **AND** records the re-search and its source-tier mix in the audit trail

#### Scenario: Re-search is bounded, not a loop

- **WHEN** the floor is still unmet after the configured number of extra passes
- **THEN** the system stops re-searching and does not loop

### Requirement: Floor-not-met emits a loud, surfaced caveat

The system SHALL, when the evidence-mix floor is still not met after the bounded re-search,
proceed but emit a loud `evidence-mix-floor-not-met` caveat that is recorded in the audit
trail AND surfaced in the final advice. The system MUST NOT pass silently.

#### Scenario: Caveat is logged and shown

- **WHEN** a candidate remains below the evidence-mix floor after re-search
- **THEN** an `evidence-mix-floor-not-met` event is written to the audit trail
- **AND** the final advice surfaces the caveat for that candidate

### Requirement: Advice disambiguates "nothing failed" from "insufficient trustworthy sources"

The final advice SHALL make explicit, for the Avoid section and for any candidate, whether a
clean result means "sufficient trusted sources were searched and nothing disqualifying was
found" versus "we did not find trustworthy enough sources to judge". These two states MUST
NOT be presented identically.

#### Scenario: Clean Avoid section is unambiguous

- **WHEN** no candidate was disqualified
- **THEN** the advice states whether that is because trusted sources were searched and found
  no disqualifying failure, or because the evidence-mix floor was not met
- **AND** a reader cannot confuse the two
