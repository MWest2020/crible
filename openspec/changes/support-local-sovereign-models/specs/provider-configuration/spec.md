## ADDED Requirements

### Requirement: OpenAI-compatible provider for local/sovereign models

The system SHALL support an OpenAI-compatible provider (for Ollama / vLLM / llama.cpp and any
OpenAI-compatible endpoint) selected by configuration, with a required `base_url` and an
optional API key. The Anthropic provider SHALL remain the default; selecting a provider MUST
NOT require code changes.

#### Scenario: Operator selects a local model

- **WHEN** the operator configures the OpenAI-compatible provider with a `base_url` and model
- **THEN** the run uses that endpoint for reasoning
- **AND** no Anthropic API key is required for that run

#### Scenario: Missing base_url fails fast

- **WHEN** the OpenAI-compatible provider is selected without a `base_url`
- **THEN** the system stops before any model call and reports the missing endpoint

### Requirement: Search mode is configurable and decoupled from provider

The system SHALL expose a `search_mode` of `server` or `client`. `server` (provider's
server-side search) is available only with the Anthropic provider; `client` (the pluggable
client-side search) works with any provider. The effective provider, model, search mode and
backend SHALL be recorded in the audit trail.

#### Scenario: Local model uses client search

- **WHEN** the provider is the OpenAI-compatible provider
- **THEN** the run uses `search_mode=client` with the configured backend
- **AND** the effective combination is recorded in the audit trail

#### Scenario: Server search requires Anthropic

- **WHEN** `search_mode=server` is configured with a non-Anthropic provider
- **THEN** the system reports the invalid combination rather than failing mid-run

### Requirement: Credentials and endpoints stay in explicit config

The OpenAI-compatible provider's `base_url`, optional key, and any search-backend keys SHALL
come from environment/config and MUST NOT be hardcoded or written to the audit trail.

#### Scenario: No endpoint or key appears in the trail

- **WHEN** a local/sovereign run completes
- **THEN** the audit trail records the base_url host for provenance but no API key or token
  value
