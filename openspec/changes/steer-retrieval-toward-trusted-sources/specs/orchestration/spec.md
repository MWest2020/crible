## ADDED Requirements

### Requirement: Domain-steered dual-pass search

The system SHALL steer `web_search` using domain lists derived from the seed tier list,
running two passes per research step: a high-trust pass whose `allowed_domains` is the
domain-listed high+medium sources, and an open pass whose `blocked_domains` is the known
affiliate/blog domains. The system SHALL document the `allowed_domains` limitation — it
covers only domain-listed sources, NOT the regex/path forum rules — and MUST NOT rely on the
allow-list alone for high-trust coverage.

#### Scenario: High-trust pass uses the allow-list

- **WHEN** a research step runs
- **THEN** a high-trust pass is issued with `allowed_domains` set to the domain-listed
  high+medium entries from the tier list
- **AND** the allowed domains for that pass are recorded in the audit trail

#### Scenario: Open pass blocks known affiliate/blog domains

- **WHEN** the open pass runs
- **THEN** its `blocked_domains` includes the known affiliate/blog domains
- **AND** the blocked domains for that pass are recorded in the audit trail

#### Scenario: Regex/path fora are not assumed covered by the allow-list

- **WHEN** the tier list contains regex/path-based forum rules (e.g. `/forum/`)
- **THEN** the system relies on the open pass plus query augmentation to reach them
- **AND** does not silently exclude them by allow-listing only named domains

#### Scenario: Provider rejects domain steering

- **WHEN** the configured provider rejects `allowed_domains`/`blocked_domains`
- **THEN** the system proceeds without domain steering and records a note explaining the
  degradation, rather than failing the run

### Requirement: Deterministic forum/review query augmentation

The system SHALL augment each subagent search with deterministic, configurable query
templates that bias toward lived experience (e.g. the "reddit" desire-path, `site:` operators
for the listed specialist fora, and "review"/"long-term" phrasing). The templates applied
SHALL be recorded in the audit trail.

#### Scenario: Augmented queries target fora and reviews

- **WHEN** a subagent searches for a candidate against a disqualifier
- **THEN** the system issues templated queries biased toward fora and user reviews in
  addition to the plain query
- **AND** records which templates were applied

#### Scenario: Templates are configurable

- **WHEN** the operator edits the query-template configuration
- **THEN** subsequent runs use the updated templates without code changes
