## ADDED Requirements

### Requirement: Apply within-source skepticism to all sources, including high-trust ones

The system SHALL NOT trust any single source blindly, high-trust sources included. It SHALL
apply per-run, signal-based skepticism inside sources to detect manipulation such as
parasite-SEO, bought upvotes/karma, astroturfing/shilling, and AI-generated reviews.

#### Scenario: A single enthusiastic post is not treated as evidence

- **WHEN** exactly one enthusiastic post praises a candidate and no independent source
  corroborates it
- **THEN** the system does not treat that post as evidence for the candidate
- **AND** records that the claim lacks independent corroboration in the audit trail

#### Scenario: Manipulation signal lowers confidence in a high-trust source

- **WHEN** posts in an otherwise high-trust forum show manipulation signals (e.g. repeated
  identical phrasing, very young accounts, a sudden cluster of praise)
- **THEN** the system reduces the weight of those posts and records the specific signals
  observed

### Requirement: Count independent corroborations as the unit of evidence

The system SHALL weigh a claim by the number of INDEPENDENT corroborations, not by volume
or enthusiasm. Independence SHALL be judged by explicit signals such as distinct accounts,
distinct sources, non-identical phrasing, and spread over time.

#### Scenario: Independent corroborations are counted

- **WHEN** several distinct accounts across distinct sources report the same failure mode in
  their own words over time
- **THEN** the system records a corroboration count reflecting the number of independent
  reports
- **AND** that count is available to the ranking step

#### Scenario: Coordinated identical reports are not counted as independent

- **WHEN** multiple reports repeat near-identical phrasing within a short cluster
- **THEN** the system does not count them as independent corroborations and records why

### Requirement: Every skepticism rule applied is explicit and logged

Each skepticism rule SHALL be explicit (not a black-box heuristic) and every rule that fires
MUST be written to the audit trail, naming the rule and the signal that triggered it.

#### Scenario: Applied rule is recorded

- **WHEN** any skepticism rule fires during a run
- **THEN** the audit trail contains an entry naming the rule, the source/post it applied to,
  and the signal that triggered it
