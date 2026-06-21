## ADDED Requirements

### Requirement: Quotes in the advice are verified present on the live page

The final advice SHALL only display a quote that has been verified to appear on the fetched
content of its cited live page (when content fetching is enabled). A quote that could not be
grounded against page content MUST NOT be presented as evidence.

#### Scenario: Advice shows only grounded quotes

- **WHEN** content fetching is enabled and the advice shows a finding's quote
- **THEN** that quote was verified present on the cited page's fetched text

#### Scenario: Ungrounded finding does not reach the advice

- **WHEN** a finding's quote could not be verified on any cited page
- **THEN** the finding does not appear in the advice
