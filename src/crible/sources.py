# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/sources.py — explainable source-trust classification.
#
# Loads the seeded tier list and classifies a URL into "high" / "low" /
# "unknown" by matching explicit rules. Every classification returns the rule
# id that produced it, so the audit trail can show *why* — never a black-box
# score. This is the central "boring, auditable" choice (design D3).
#
# Writes: read-only
# Idempotent: yes
# Requires: pyyaml; the seed file at the configured path

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .models import Source


class TierListError(RuntimeError):
    """Raised when the seed tier list is missing or malformed."""


@dataclass
class _Rule:
    id: str
    tier: str
    match: str  # "domain" | "regex"
    patterns: list[str]
    note: str = ""
    _compiled: list[re.Pattern] | None = None

    def compile(self) -> None:
        if self.match == "regex":
            self._compiled = [re.compile(p) for p in self.patterns]

    def matches(self, url: str, host: str) -> bool:
        if self.match == "domain":
            return any(p.lower() in host for p in self.patterns)
        if self.match == "regex":
            return any(rx.search(url) for rx in (self._compiled or []))
        raise TierListError(f"rule {self.id}: unknown match type {self.match!r}")


class TierList:
    """The seeded trust-tier classifier."""

    def __init__(self, high: list[_Rule], low: list[_Rule]) -> None:
        # High rules are evaluated before low rules (first match wins).
        self._rules = high + low

    @classmethod
    def load(cls, path: Path) -> TierList:
        path = Path(path)
        if not path.exists():
            raise TierListError(f"source tier list not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        high = cls._parse(data.get("high", []), "high")
        low = cls._parse(data.get("low", []), "low")
        return cls(high, low)

    @staticmethod
    def _parse(entries: list[dict], tier: str) -> list[_Rule]:
        rules: list[_Rule] = []
        for entry in entries:
            rule = _Rule(
                id=entry["id"],
                tier=tier,
                match=entry.get("match", "domain"),
                patterns=list(entry.get("patterns", [])),
                note=entry.get("note", ""),
            )
            rule.compile()
            rules.append(rule)
        return rules

    def classify(self, url: str, title: str = "") -> Source:
        """Return a Source with its tier and the matching rule id (or 'unmatched')."""
        host = (urlparse(url).hostname or "").lower()
        for rule in self._rules:
            if rule.matches(url, host):
                return Source(url=url, title=title, tier=rule.tier, tier_rule=rule.id)
        return Source(url=url, title=title, tier="unknown", tier_rule="unmatched")
