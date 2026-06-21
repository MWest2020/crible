## ADDED Requirements

### Requirement: Extract positive requirements, disqualifiers, budget and context

The system SHALL derive from the user's question a structured criteria set containing:
positive requirements, NEGATIVE requirements (disqualifiers), budget, and usage context.
Disqualifiers SHALL be treated as first-class criteria, not as an afterthought.

#### Scenario: Question contains an explicit disqualifier

- **WHEN** the user asks for "a travel thermos for quality coffee, but no metallic taste"
- **THEN** the system records `metallic taste` as a disqualifier and `keeps coffee hot
  on the go` / `quality coffee` as positive requirements
- **AND** both the positive requirements and the disqualifier are written to the audit trail

#### Scenario: Budget and context are captured when stated

- **WHEN** the user states a price ceiling and an intended use ("under €40, for daily
  commuting")
- **THEN** the system records budget `≤ €40` and context `daily commuting` as part of the
  criteria set

### Requirement: Ask back when a disqualifier is missing

The system SHALL detect when the question implies a likely disqualifier that the user has
not stated, and SHALL ask a clarifying question before proceeding, rather than silently
assuming one.

#### Scenario: No disqualifier provided for a category known for failure modes

- **WHEN** the user asks only "what is the best travel thermos?" with no negative
  requirement
- **THEN** the system asks back at least one clarifying question about common failure modes
  (e.g. "do you care about metallic taste, leaking, or weight?")
- **AND** the system does not proceed to ranking until it has either an answer or an
  explicit user instruction to continue without a disqualifier

#### Scenario: User declines to add a disqualifier

- **WHEN** the user is asked for a disqualifier and replies that they have none
- **THEN** the system records `disqualifiers: none (user-confirmed)` in the audit trail
  and proceeds

### Requirement: Scale extraction effort to question complexity

The system SHALL scale the depth of criteria extraction to the complexity of the question
and MUST NOT run a heavy clarification loop for a trivial question.

#### Scenario: Trivial question

- **WHEN** the question is simple and fully specified (single criterion, clear category)
- **THEN** the system performs a single-pass extraction with no clarification round

#### Scenario: Complex question

- **WHEN** the question has multiple competing requirements and an implied disqualifier
- **THEN** the system performs a deeper extraction and asks back on the missing
  disqualifier before planning the research
