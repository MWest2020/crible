## ADDED Requirements

### Requirement: Model and provider are configurable (sovereign/cloud split)

The system SHALL make the model and provider configurable, supporting a sovereign/cloud
split, via explicit configuration. The backend SHALL use the Anthropic Messages API with the
`web_search` tool in an agentic tool-use loop.

#### Scenario: Operator selects provider and model via config

- **WHEN** the operator sets the provider and model in configuration
- **THEN** the run uses the configured provider and model without code changes

### Requirement: API keys come from explicit config, never hardcoded

API keys and credentials SHALL be read at runtime from environment variables or a vault
reference. They MUST NOT be hardcoded in source and MUST NOT be written to logs or the audit
trail.

#### Scenario: Missing credential fails fast with a clear message

- **WHEN** a run starts without the required API key available in the environment/vault
- **THEN** the system stops before issuing any API call and reports that the credential is
  missing
- **AND** no credential value is printed

#### Scenario: No credential appears in source or logs

- **WHEN** the source tree and run logs are inspected
- **THEN** no API key or token literal is present

### Requirement: Run-level limits and parallelisation are configurable

The system SHALL expose the cumulative token ceiling, the parallelisation switch, and the
independent-corroboration threshold as explicit configuration with safe defaults:
parallelisation defaults to OFF, a token ceiling is always set, and the corroboration
threshold defaults to ≥ 2.

#### Scenario: Defaults are safe when nothing is configured

- **WHEN** a run starts with no explicit limit/parallelisation settings
- **THEN** parallelisation is OFF, a default token ceiling is in effect, and the
  corroboration threshold is ≥ 2
- **AND** the effective settings are recorded in the audit trail

#### Scenario: Operator overrides the corroboration threshold

- **WHEN** the operator sets the corroboration threshold in configuration
- **THEN** the run requires that many independent corroborations before a claim or failure
  mode may affect ranking
- **AND** the effective threshold is recorded in the audit trail
