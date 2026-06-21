## ADDED Requirements

### Requirement: Link-check outcomes are recorded

The system SHALL record link-liveness decisions in the audit trail: every dropped dead link
(with its URL and reason) and every finding dropped for lack of a live source. The run SHALL
remain reconstructable — a reader can see which citations were rejected and why.

#### Scenario: Dropped link is in the trail

- **WHEN** a source is dropped as a dead link
- **THEN** the audit trail contains an entry naming the URL and the reason
