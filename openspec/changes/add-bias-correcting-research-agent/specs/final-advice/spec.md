## ADDED Requirements

### Requirement: Every recommendation and rejection carries grounding

The system SHALL attach to every recommendation AND every rejection: source reference(s), an
independent-corroboration count, and a reason. No claim SHALL be made without grounding —
no grounding = no claim.

#### Scenario: Recommendation includes grounding

- **WHEN** the final advice recommends a product
- **THEN** it states the reason, the supporting source links, and the independent-corroboration
  count behind the recommendation

#### Scenario: Rejection includes grounding

- **WHEN** the final advice rejects a product
- **THEN** it states the failure mode, the independent high-trust sources reporting it, and
  the corroboration count

#### Scenario: An ungrounded claim is omitted

- **WHEN** a candidate cannot be supported or rejected with at least one source after the
  verification pass
- **THEN** the system omits the claim rather than presenting it as advice

### Requirement: Final advice follows the prescribed format

The final advice SHALL follow the form: "This fits best, because X (n sources). Avoid Y,
because Z independent users report <failure mode>.", with direct source links.

#### Scenario: Advice matches the worked example shape

- **WHEN** the user asked for a travel thermos with no metallic taste
- **THEN** the advice names the best-fitting model(s) with a reason and source count, and
  names avoided models with the metallic-taste failure mode, its corroboration count, and
  direct links
- **AND** every recommended model has no metallic-taste failure mode corroborated in
  independent high-trust sources

### Requirement: Advice is consistent with the audit trail

The final advice MUST be consistent with the audit trail: every claim in the advice SHALL be
traceable to entries in the JSONL trail for the same run.

#### Scenario: Advice claims trace to the trail

- **WHEN** any claim in the final advice is checked
- **THEN** the corresponding source classification, corroboration count and score exist in
  the run's audit trail
