## ADDED Requirements

### Requirement: Write a per-run JSONL audit trail

The system SHALL write a per-run audit trail as JSONL (one JSON object per line, append-only)
capturing at minimum: queries issued, sources visited, source classifications, skepticism
rules applied, corroboration counts, scores, and the final decision. The trail MUST be
sufficient to reconstruct the run.

#### Scenario: A run produces a reconstructable trail

- **WHEN** a run completes
- **THEN** a JSONL file exists for that run containing the queries, visited sources, their
  classifications, skepticism rules applied, corroboration counts, scores and the final
  decision
- **AND** a reader can reconstruct why each candidate was recommended or rejected from the
  trail alone

#### Scenario: Each event is an independent JSON line

- **WHEN** the audit trail is read
- **THEN** every line parses as a standalone JSON object with a type and timestamp
- **AND** lines are append-only (no rewriting of earlier events)

### Requirement: Audit trail never contains secrets

The audit trail MUST NOT contain API keys, tokens, or other credentials.

#### Scenario: Credentials are absent from the trail

- **WHEN** the audit trail is inspected after a run
- **THEN** no API key, token, or credential value appears anywhere in it

### Requirement: Verification pass produces the trail as a by-product

The separate verification/citation pass SHALL emit the grounding portion of the audit trail,
so the record cannot drift from the decision it documents.

#### Scenario: Every claim in the trail has a source

- **WHEN** the verification pass runs
- **THEN** each recommendation/rejection claim recorded in the trail carries the source
  reference(s) that ground it
- **AND** any claim that cannot be grounded is dropped rather than recorded as supported
