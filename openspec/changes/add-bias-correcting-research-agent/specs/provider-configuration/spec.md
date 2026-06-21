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

### Requirement: Run-level cost and parallelisation are configurable

The token/cost ceiling and the parallelisation switch SHALL be explicit configuration with
safe defaults: parallelisation defaults to OFF and a cost ceiling is always set.

#### Scenario: Defaults are safe when nothing is configured

- **WHEN** a run starts with no explicit cost/parallelisation settings
- **THEN** parallelisation is OFF and a default cost ceiling is in effect
- **AND** the effective settings are recorded in the audit trail
