## ADDED Requirements

### Requirement: Rank by source-trust × independent-corroboration × failure-severity

The system SHALL rank candidates as a transparent function of three logged inputs:
source trust, independent-corroboration count, and failure-mode severity. Ranking MUST NOT
be driven by marketing sentiment or by the raw volume of positive text.

#### Scenario: Ranking inputs are all auditable

- **WHEN** the system produces a ranked list
- **THEN** each candidate's position is explained by its source-trust, corroboration count
  and failure-severity values
- **AND** all three input values for each candidate are present in the audit trail

#### Scenario: A heavily marketed product does not outrank a corroborated one

- **WHEN** candidate A has abundant positive marketing/SEO text but a disqualifying failure
  mode corroborated by independent high-trust sources, and candidate B has fewer mentions
  but no disqualifying failure mode
- **THEN** candidate B ranks above candidate A

### Requirement: Ranking is never influenced by commercial incentive

As a hard design principle independent of any business model, ranking MUST NOT be influenced
by commercial incentive. The system SHALL NOT use affiliate links, commission-weighted
ordering, or sponsored placement, and the order SHALL follow solely from source-trust ×
corroboration × failure-severity.

#### Scenario: No commercial signal enters the ranking

- **WHEN** ranking is computed
- **THEN** no affiliate, commission, sponsorship, or merchant-revenue signal is an input to
  the ordering
- **AND** the presence of any such coupling is a specification violation

#### Scenario: Donation/credit does not affect ranking

- **WHEN** the project displays a voluntary donation prompt or attribution/credit
- **THEN** that has no effect on which products are recommended or on their order

### Requirement: Reject the merchant-side recommender anti-pattern

The system MUST NOT implement a merchant-side recommender (collaborative filtering,
content-based filtering, hybrid models, or clustering such as k-means over product
descriptions) as the basis for its recommendations.

#### Scenario: Ranking basis is provenance and corroboration, not surface similarity

- **WHEN** the ranking method is inspected
- **THEN** it is based on source provenance, independent corroboration and failure severity
- **AND** it is not based on behavioural/textual surface-similarity matching optimised for
  conversion
