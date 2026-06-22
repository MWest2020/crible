## ADDED Requirements

### Requirement: Client-side discovery surfaces URLs the provider misses

The system SHALL provide a client-side discovery step that, given a query, returns candidate
URLs from sources the provider's web_search does not surface — at minimum a reddit backend
that returns reddit thread URLs for the query. The backend SHALL be pluggable and configurable,
and discovery SHALL be bounded by a configurable maximum number of results and cached per run.

#### Scenario: Reddit threads are discovered for a query

- **WHEN** discovery runs for a query on the reddit backend
- **THEN** it returns reddit thread URLs relevant to the query
- **AND** those URLs are recorded in the audit trail

#### Scenario: Discovery is bounded and cached

- **WHEN** discovery is invoked repeatedly for the same query in a run
- **THEN** results are cached and the number returned does not exceed the configured maximum

### Requirement: Discovered URLs feed the existing fetch + verify pipeline

Discovered URLs SHALL be merged with the provider's web_search results and run through the
same fetch, classification, and quote-verification path — so a discovered reddit thread that
is client-fetchable and quote-verified becomes evidence exactly like any other source.

#### Scenario: A discovered reddit thread becomes evidence

- **WHEN** a discovered reddit thread is fetched and a verbatim quote is verified against it
- **THEN** that finding is recorded with the reddit URL and its high trust tier, like any other
  credible source

### Requirement: Discovery is degradable and never fails the run

The system SHALL treat a discovery backend error (rate-limit, block, timeout) as non-fatal:
it records the failure and proceeds on the provider's web_search results alone. Discovery
SHALL be toggleable via configuration (default on).

#### Scenario: Reddit blocks the discovery request

- **WHEN** the reddit backend returns an error or is rate-limited
- **THEN** the system records the degradation and continues the run without discovery results

#### Scenario: Discovery disabled

- **WHEN** discovery is turned off in configuration
- **THEN** the run uses only the provider's web_search results, as before
