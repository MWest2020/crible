## ADDED Requirements

### Requirement: Classify every source into an explainable trust tier

The system SHALL classify every visited source into a trust tier using a seeded,
version-controlled tier list (allow/deny per source type). Low-trust types include
manufacturer sites, webshops, affiliate blogs, top-10 lists, and sponsored/SEO content.
High-trust types include topic-specific specialist forums and communities, lived-experience
reports, and repeated independent reports. The classification of each source and the rule
that produced it MUST be recorded in the audit trail.

#### Scenario: Affiliate blog is classified low-trust

- **WHEN** a visited source matches an affiliate-blog / top-10-list pattern in the seed list
- **THEN** the system classifies it as `low` trust
- **AND** records the source, its assigned tier, and the matching rule in the audit trail

#### Scenario: Topic-specific forum is classified high-trust

- **WHEN** a visited source matches a specialist-forum / community pattern for the question's
  topic
- **THEN** the system classifies it as `high` trust
- **AND** records the source, its assigned tier, and the matching rule in the audit trail

### Requirement: Trust classification uses no learned black-box score

The system MUST NOT determine source trust with a learned, unexplainable scoring model.
The tier assignment SHALL be reducible to an explicit rule in the seed list that a human can
read and audit.

#### Scenario: Every classification traces to an explicit rule

- **WHEN** any source is classified
- **THEN** the audit trail entry references the specific seed-list rule (pattern/source-type)
  that produced the tier
- **AND** no classification is attributable to an opaque model output

### Requirement: Trust-tier seed list is explicit configuration

The seed tier list SHALL be explicit configuration (version-controlled), editable without
code changes, so that misclassifications can be corrected and the change is auditable.

#### Scenario: Operator corrects a misclassification

- **WHEN** the operator adds or edits a pattern in the seed tier list
- **THEN** subsequent runs classify matching sources according to the updated list
- **AND** no application code change is required for the correction
