## ADDED Requirements

### Requirement: Client-side search tool with a pluggable backend

The system SHALL provide a client-side `web_search` tool that the agent loop executes itself
(not a provider server tool), backed by a configurable search backend. At least one
self-hosted/sovereign backend (SearXNG) and the option of a cloud backend SHALL be supported.
The selected backend MUST come from explicit configuration.

#### Scenario: Client search returns normalised sources

- **WHEN** the agent issues a `web_search` tool call in client mode
- **THEN** the configured backend is queried and results are returned as sources with at least
  url and title
- **AND** those sources flow through the existing classification, skepticism, ranking and
  evidence-mix steps unchanged

#### Scenario: Sovereign backend keeps reasoning local

- **WHEN** the backend is a self-hosted SearXNG instance and the provider is a local model
- **THEN** the only outbound network traffic for retrieval is SearXNG's own web queries
- **AND** the question and the model's reasoning are not sent to any third-party LLM provider

#### Scenario: Backend choice is explicit and logged

- **WHEN** a run uses client-side search
- **THEN** the configured backend is recorded in the audit trail
- **AND** if no backend is configured, the system reports the misconfiguration rather than
  silently running without search

### Requirement: Bounded, logged client search calls

The system SHALL bound client-side search (and any optional fetch) by the existing per-thread
iteration/tool-call limits, and SHALL log each client search call (query, backend, result
count) to the audit trail like a server query.

#### Scenario: Client search respects the per-thread bound

- **WHEN** the agent would exceed the configured per-thread tool-call bound
- **THEN** the system stops issuing client search calls for that thread

#### Scenario: Backend failure is logged, not silent

- **WHEN** the search backend errors or times out
- **THEN** the system records the error in the audit trail and proceeds with what it has
- **AND** the evidence-mix floor surfaces any resulting thinness as a caveat
