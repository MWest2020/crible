## ADDED Requirements

### Requirement: Do not systematically favour the most popular products

The system MUST NOT reward popularity as such. Mention volume or market prominence SHALL NOT
be an input to ranking, so that a niche product can win when it best satisfies the criteria
and avoids the disqualifiers.

#### Scenario: A niche product wins on the disqualifier

- **WHEN** a popular product carries a disqualifying failure mode and a niche product avoids
  it while meeting the positive requirements
- **THEN** the niche product ranks above the popular product

#### Scenario: Popularity is not a ranking input

- **WHEN** ranking is computed
- **THEN** neither mention volume nor market popularity appears as an input to the order

### Requirement: Build a candidate set broad enough to include long-tail options

The system SHALL build a candidate landscape that deliberately includes niche/long-tail
options, not only the products that surface first in mainstream search.

#### Scenario: Candidate set includes long-tail entries

- **WHEN** the LEAD agent builds the candidate landscape
- **THEN** the set includes candidates sourced from high-trust specialist communities, not
  only mainstream top-10 lists
- **AND** the provenance of each candidate is recorded in the audit trail
