# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/models.py — core data structures for the research run.
#
# Plain dataclasses shared across the pipeline. No behaviour here beyond simple
# serialisation helpers, so the shapes stay auditable and easy to log as JSONL.
#
# Writes: read-only (pure data)
# Idempotent: yes
# Requires: stdlib only

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Criteria:
    """The structured criteria extracted from the user's question."""

    question: str
    positive: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)
    budget: str | None = None
    context: str | None = None
    clarification_needed: str | None = None  # set when a disqualifier is missing

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Source:
    """A single visited source with its trust classification."""

    url: str
    title: str = ""
    tier: str = "unknown"  # "low" | "high" | "unknown"
    tier_rule: str = ""  # the seed-list rule that produced the tier

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """A condensed finding about one candidate, returned by a subagent thread."""

    candidate: str
    kind: str  # "failure" | "support"
    claim: str
    severity: str = "unknown"  # "disqualifying" | "minor" | "unknown" (failures only)
    sources: list[Source] = field(default_factory=list)
    corroboration_count: int = 0
    skepticism_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = [s.to_dict() for s in self.sources]
        return d


@dataclass
class Candidate:
    """A product under consideration, with its provenance and accumulated findings."""

    name: str
    provenance: str = ""  # where the candidate came from (audit)
    findings: list[Finding] = field(default_factory=list)
    score: float = 0.0
    disqualified: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d
