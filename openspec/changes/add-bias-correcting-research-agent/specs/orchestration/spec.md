## ADDED Requirements

### Requirement: Orchestrator-worker flow with a separate verification pass

The system SHALL implement an orchestrator-worker research flow, not a single-shot prompt,
with these stages: (1) LEAD criteria extraction; (2) LEAD landscape + plan, with the plan
persisted to external memory; (3) subagents, each exploring one independent thread in its
own context and returning condensed findings; (4) LEAD weighting + ranking; (5) a SEPARATE
verification/citation pass; (6) final advice.

#### Scenario: A run executes the staged flow

- **WHEN** a research run is started
- **THEN** the system runs criteria extraction, landscape+plan, subagent exploration,
  weighting+ranking, a separate verification pass, and final advice, in that order
- **AND** the plan is persisted to external memory so it survives a long run

#### Scenario: Subagents return condensed findings in isolated context

- **WHEN** a subagent explores its thread
- **THEN** it operates in its own context and returns condensed findings to the LEAD agent
  rather than its full transcript

### Requirement: Single-threaded by default, parallelisation behind an explicit switch

The system SHALL execute subagent threads single-threaded by default. Parallel execution
SHALL be available only via an explicit configuration switch that defaults to OFF.

#### Scenario: Default run is single-threaded

- **WHEN** a run starts with no parallelisation configuration
- **THEN** subagent threads execute sequentially

#### Scenario: Parallelisation requires an explicit opt-in

- **WHEN** the operator sets the parallelisation switch to enabled
- **THEN** the system may run subagents in parallel, subject to the subagent cap
- **AND** the audit trail records that parallel mode was active

### Requirement: Cap subagents and scale effort to complexity

The system SHALL enforce a maximum number of subagents per run and SHALL scale the number of
threads to the question's complexity, so a trivial question does not spawn a heavy fan-out.

#### Scenario: Trivial question spawns minimal threads

- **WHEN** the question is simple and fully specified
- **THEN** the system spawns at most a small number of threads, well below the cap

#### Scenario: Subagent cap is enforced

- **WHEN** planning would exceed the configured subagent cap
- **THEN** the system limits the number of subagents to the cap and records the limit in the
  audit trail

### Requirement: Bound iterations and tool-calls per thread with explicit stop conditions

The system SHALL bound the number of iterations and tool-calls per research thread and SHALL
define explicit stop conditions, so a thread cannot loop indefinitely searching for sources
that do not exist.

#### Scenario: Thread hits its iteration bound

- **WHEN** a thread reaches its configured iteration/tool-call bound without satisfying its
  stop condition
- **THEN** the thread stops, returns what it has, and records that it stopped on the bound

### Requirement: Deduplicate queries and sources

The system SHALL deduplicate redundant queries and already-visited sources across threads to
avoid wasted tool-calls and tokens.

#### Scenario: Redundant query is skipped

- **WHEN** a thread is about to issue a query equivalent to one already executed in the run
- **THEN** the system skips the redundant query and reuses the prior result
- **AND** records the dedup decision in the audit trail

### Requirement: Enforce a configurable cost/token ceiling

The system SHALL enforce an explicit, configurable cumulative token ceiling per run and SHALL
halt the run when the ceiling is reached, returning the best result available so far. The
ceiling is token-based (provider-independent); a monetary/USD cap is out of scope for the MVP.

#### Scenario: Cost ceiling halts the run

- **WHEN** cumulative token/cost usage reaches the configured ceiling
- **THEN** the system halts further work and produces advice from findings gathered so far
- **AND** records that the run stopped on the cost ceiling
