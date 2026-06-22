## ADDED Requirements

### Requirement: Retrieval augments provider search with client discovery

The landscape and subagent retrieval stages SHALL, when discovery is enabled, merge
client-discovered URLs with the provider's web_search results before the fetch/extract step —
so candidate discovery and evidence gathering both benefit from sources the provider misses
(notably reddit). Discovery SHALL respect the run's bounds and stay single-threaded.

#### Scenario: Subagent evidence includes discovered sources

- **WHEN** a subagent investigates a candidate with discovery enabled
- **THEN** the URLs it fetches include client-discovered reddit/forum URLs in addition to the
  provider's web_search results

#### Scenario: Landscape uses discovered community discussion

- **WHEN** the landscape stage builds the candidate set with discovery enabled
- **THEN** it incorporates products discussed in client-discovered community threads
