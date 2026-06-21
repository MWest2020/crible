## ADDED Requirements

### Requirement: Actively hunt candidate failure modes in high-trust sources

The system SHALL actively search for the ways each candidate FAILS — not only for positive
matches — focusing on high-trust sources. Failure-mode detection SHALL be explicitly tied to
the disqualifiers extracted from the question.

#### Scenario: Search targets the disqualifier

- **WHEN** the criteria set contains the disqualifier "metallic taste" for a thermos
- **THEN** at least one research thread issues queries aimed at finding reports of metallic
  taste for each candidate in high-trust sources
- **AND** the queries and their target candidate are recorded in the audit trail

#### Scenario: Candidate fails the disqualifier in independent high-trust sources

- **WHEN** the disqualifying failure mode is reported by independent high-trust sources at or
  above the corroboration threshold (default ≥ 2 independent, configurable)
- **THEN** the system marks the candidate as disqualified
- **AND** records the failure mode, the corroborating sources, and the corroboration count

### Requirement: Assess severity of each detected failure mode

The system SHALL record a severity for each detected failure mode so that ranking can weigh
how badly a candidate fails, not merely whether a complaint exists.

#### Scenario: Severity is recorded with the failure mode

- **WHEN** a failure mode is detected for a candidate
- **THEN** the system records a severity assessment (e.g. disqualifying vs minor) together
  with the supporting sources
- **AND** that severity is available to the ranking step

### Requirement: Distinguish absence of evidence from evidence of absence

The system SHALL distinguish "no failure reports found" from "failure mode confirmed absent"
and MUST NOT treat a lack of complaints as proof a candidate is safe.

#### Scenario: No reports found for a candidate

- **WHEN** no failure reports are found for a candidate after a bounded search
- **THEN** the system records `failure mode: not found (searched, bounded)` rather than
  asserting the candidate is free of the failure mode
