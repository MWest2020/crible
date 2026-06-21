# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/skepticism.py — within-source skepticism and corroboration counting.
#
# Independent corroboration is the unit of evidence (design D4) — but only
# CREDIBLE evidence counts. Blogs / affiliate / marketing (low) and unclassified
# (unknown) sources are an echo chamber: ten of them is not corroboration, it is
# one affiliate line copied ten times. So corroboration counts only high (fora /
# discussion) and medium (user reviews) sources. A blog-only finding gets a
# corroboration count of zero and cannot support a recommendation.
#
# Writes: read-only
# Idempotent: yes
# Requires: stdlib + the TierList classifier

from __future__ import annotations

from urllib.parse import urlparse

from .models import Finding, Source
from .sources import TierList

# Tiers that count as real evidence. Since findings are now grounded in a
# verbatim quote VERIFIED against the fetched page (pre-fetch → extract), a real
# user-experience quote counts even from a forum/review the seed list doesn't
# name (unknown). Only explicit "low" (affiliate / manufacturer / top-10 / SEO)
# stays mere context — never proof on its own.
CREDIBLE_TIERS = ("high", "medium", "unknown")

# Cap on the model-reported corroboration count, to bound hallucinated inflation.
_MAX_CORROBORATION = 25

# Explicit skepticism rules (names recorded in the audit trail when they fire).
RULE_SINGLE_SOURCE = "single-source-not-evidence"
RULE_BELOW_THRESHOLD = "below-corroboration-threshold"
RULE_NO_HIGH_TRUST = "no-high-trust-corroboration"
RULE_NO_CREDIBLE = "no-credible-source-echo-chamber"


def _host(url: str) -> str:
    return (urlparse(url).hostname or url).lower()


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


def credible_sources(sources: list[Source]) -> list[Source]:
    """Sources that count as evidence (fora / discussion + user reviews)."""
    return [s for s in sources if s.tier in CREDIBLE_TIERS]


def count_independent(sources: list[Source]) -> int:
    """Independent corroborations = distinct CREDIBLE hostnames.

    Blogs / marketing / unknown are excluded — they are an echo chamber and do
    not corroborate anything.
    """
    return len({_host(s.url) for s in sources if s.tier in CREDIBLE_TIERS})


def evaluate_finding(finding: Finding, threshold: int) -> list[str]:
    """Apply skepticism rules; return the rule ids that fired.

    Sets finding.corroboration_count to a credible-only value: zero if no
    credible source backs it (echo chamber), otherwise the larger of the number
    of distinct credible hosts and the model-reported independent-account count
    (capped) — so genuine multi-reviewer / multi-thread evidence is honoured but
    blog volume is not.
    """
    fired: list[str] = []
    credible = credible_sources(finding.sources)
    distinct_hosts = len({_host(s.url) for s in credible})
    reported = max(0, int(finding.corroboration_count))

    if not credible:
        finding.corroboration_count = 0
        fired.append(RULE_NO_CREDIBLE)
    else:
        finding.corroboration_count = max(distinct_hosts, min(reported, _MAX_CORROBORATION))

    independent = finding.corroboration_count
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
