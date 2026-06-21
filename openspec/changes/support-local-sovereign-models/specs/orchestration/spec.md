## ADDED Requirements

### Requirement: Research abstracts over server-side and client-side search

The orchestrator's research step SHALL operate through a provider abstraction so it works
unchanged whether retrieval is a provider server tool (server mode) or the client-side search
tool (client mode). Downstream stages (classification, skepticism, ranking, evidence-mix,
advice) MUST consume the same normalised sources regardless of search mode.

#### Scenario: Same pipeline for both search modes

- **WHEN** a run uses client-side search instead of the server tool
- **THEN** the candidate landscape, subagent investigation, ranking and advice run unchanged
- **AND** the only difference is where the sources came from

### Requirement: Bounded manual tool-use loop for client mode

For client mode, the system SHALL run a bounded manual function-calling loop — present the
search/fetch tool(s), execute the model's tool calls against the backend, feed results back,
and repeat until the model stops or the per-thread iteration/tool-call bound is reached. Token
and cost accounting SHALL continue to apply against the run ceiling.

#### Scenario: Client loop honours the iteration bound

- **WHEN** the model keeps requesting tool calls in client mode
- **THEN** the loop stops at the configured per-thread iteration/tool-call bound

#### Scenario: Cost ceiling still applies in client mode

- **WHEN** cumulative usage reaches the configured token/cost ceiling during a client-mode run
- **THEN** the run halts and returns the best result so far, as in server mode
