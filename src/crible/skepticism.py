# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/skepticism.py — within-source skepticism and corroboration counting.
#
# Independent corroboration is the unit of evidence (design D4). These helpers
# count distinct sources, classify them via the seeded tier list, and decide
# whether a finding clears the configurable corroboration threshold. Every rule
# applied is explicit and returned for logging — no hidden heuristics.
#
# Writes: read-only
# Idempotent: yes
# Requires: stdlib + the TierList classifier

from __future__ import annotations

from urllib.parse import urlparse

from .models import Finding, Source
from .sources import TierList

# Explicit skepticism rules (names recorded in the audit trail when they fire).
RULE_SINGLE_SOURCE = "single-source-not-evidence"
RULE_BELOW_THRESHOLD = "below-corroboration-threshold"
RULE_NO_HIGH_TRUST = "no-high-trust-corroboration"


def classify_sources(tier_list: TierList, sources: list[Source]) -> list[Source]:
    """Classify each source, deduplicating by URL (boring dedup of evidence)."""
    seen: set[str] = set()
    out: list[Source] = []
    for src in sources:
        if src.url in seen:
            continue
        seen.add(src.url)
        out.append(tier_list.classify(src.url, src.title))
    return out


def count_independent(sources: list[Source]) -> int:
    """Count independent corroborations = distinct hostnames among the sources.

    Distinct hosts is a deliberately conservative, explainable proxy for
    independence; the LLM's own corroboration_count is cross-checked against it.
    """
    hosts = {(urlparse(s.url).hostname or s.url).lower() for s in sources}
    return len(hosts)


def evaluate_finding(finding: Finding, threshold: int) -> list[str]:
    """Apply skepticism rules to a finding; return the rule ids that fired.

    Also normalises finding.corroboration_count to the conservative
    distinct-host count so ranking never over-credits a single source.
    """
    fired: list[str] = []
    independent = count_independent(finding.sources)
    finding.corroboration_count = independent

    if independent <= 1:
        fired.append(RULE_SINGLE_SOURCE)
    if independent < threshold:
        fired.append(RULE_BELOW_THRESHOLD)
    if not any(s.tier == "high" for s in finding.sources):
        fired.append(RULE_NO_HIGH_TRUST)

    for rule in fired:
        if rule not in finding.skepticism_flags:
            finding.skepticism_flags.append(rule)
    return fired
