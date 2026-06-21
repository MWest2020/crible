## ADDED Requirements

### Requirement: Tier list exposes explicit domain allow/block lists for steering

The seed tier list SHALL expose, separately from its regex/path rules, the explicit
domain-match entries as an allow list (high+medium domains) and a block list (low-tier
affiliate/blog domains), so retrieval can be steered from the same single source of truth.
The system MUST NOT introduce a second trust source for steering.

#### Scenario: Allow/block lists are derived from the seed list

- **WHEN** the tier list is loaded
- **THEN** the system can produce the set of domain-listed high+medium domains (allow) and
  the low-tier affiliate/blog domains (block)
- **AND** both lists are derived solely from `source_tiers.yaml`

#### Scenario: Regex/path rules are kept separate from the domain lists

- **WHEN** the steering domain lists are produced
- **THEN** they contain only domain-match entries, not the regex/path forum rules
- **AND** the separation is explicit so callers know the allow-list is not exhaustive

### Requirement: Every steering decision traces to the seed list

The system SHALL ensure every allow/block steering decision is attributable to an explicit
entry in the seed tier list. There MUST be no learned or black-box component in steering.

#### Scenario: A blocked domain traces to a rule

- **WHEN** a domain is blocked on the open search pass
- **THEN** the audit trail can attribute the block to a specific low-tier seed entry
