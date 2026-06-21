## ADDED Requirements

### Requirement: Bounded fetch step feeds real page text into extraction

The orchestrator SHALL, when content fetching is enabled, fetch cited credible pages and feed
the extracted page text into finding extraction and quote verification, so quotes are taken
from and checked against real content. The fetch step SHALL respect the existing per-thread
iteration/tool-call bounds and the run token/cost ceiling, and SHALL stay single-threaded by
default (any fetch IO concurrency is bounded and separate from subagent execution).

#### Scenario: Extraction quotes from fetched text

- **WHEN** a candidate's credible sources are fetched
- **THEN** finding extraction draws quotes from the fetched page text rather than search
  snippets

#### Scenario: Fetch respects run bounds

- **WHEN** fetching would exceed the configured caps or the run cost ceiling
- **THEN** the system stops fetching and proceeds with what it has, recording the limit
