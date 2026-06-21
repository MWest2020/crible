# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/advice.py — render the final advice in the prescribed format.
#
# "This fits best, because X (n sources). Avoid Y, because Z independent users
# report <failure mode>." Every recommendation and every rejection carries
# source links and a corroboration count. No grounding = no claim, so any
# candidate without surviving findings is reported as insufficiently evidenced
# rather than recommended.
#
# Writes: read-only (returns a Markdown string; the caller persists it)
# Idempotent: yes
# Requires: stdlib + models

from __future__ import annotations

from urllib.parse import urlparse

from .models import Candidate, Criteria, Finding

_CREDIBLE_TIERS = ("high", "medium", "unknown")


def _credible_host_count(findings: list[Finding]) -> int:
    hosts = {
        (urlparse(s.url).hostname or s.url).lower()
        for f in findings
        for s in f.sources
        if s.tier in _CREDIBLE_TIERS
    }
    return len(hosts)


def _has_credible_support(cand: Candidate, threshold: int) -> bool:
    """A candidate is recommendable only with credible-grounded support."""
    return any(
        f.kind == "support"
        and f.corroboration_count >= threshold
        and any(s.tier in _CREDIBLE_TIERS for s in f.sources)
        for f in cand.findings
    )


def _links(findings: list[Finding]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        for s in f.sources:
            if s.url not in seen:
                seen.add(s.url)
                label = s.title or s.url
                out.append(f"  - [{label}]({s.url}) — trust: {s.tier}")
    return out


def render(criteria: Criteria, ranked: list[Candidate], corroboration_threshold: int = 2) -> str:
    """Produce the Markdown advice document for one run."""
    lines: list[str] = ["# Crible advice", ""]
    lines.append(f"**Question:** {criteria.question}")
    if criteria.disqualifiers:
        lines.append(f"**Disqualifiers:** {', '.join(criteria.disqualifiers)}")
    if criteria.positive:
        lines.append(f"**Requirements:** {', '.join(criteria.positive)}")
    if criteria.budget:
        lines.append(f"**Budget:** {criteria.budget}")
    lines.append("")

    rejected = [c for c in ranked if c.disqualified]
    recommended = [
        c for c in ranked
        if not c.disqualified and _has_credible_support(c, corroboration_threshold)
    ]
    # Not disqualified, but only blog/echo-chamber support — not recommendable.
    unevidenced = [
        c for c in ranked
        if not c.disqualified and not _has_credible_support(c, corroboration_threshold)
    ]

    lines.append("## Recommended")
    if not recommended:
        lines.append(
            "_No candidate has credible grounded support (fora / user reviews) to recommend._"
        )
    for cand in recommended:
        supports = [f for f in cand.findings if f.kind == "support"]
        n = _credible_host_count(supports)
        lines.append(f"### {cand.name}")
        lines.append(
            f"This fits best, because it meets the requirements "
            f"({n} independent credible sources — fora / user reviews)."
        )
        lines.append(f"_Reason:_ {cand.reason}")
        for f in supports:
            crit = f" [{f.criterion}]" if f.criterion else ""
            lines.append(f"- {f.claim}{crit} ({f.corroboration_count} independent sources)")
            if f.quote:
                lines.append(f"  > “{f.quote}”")
            lines.extend(_links([f]))
        if cand.caveat:
            lines.append(
                f"> ⚠ Caveat ({cand.caveat}): too few trusted fora / user-review sources — "
                "treat this recommendation with caution."
            )
        lines.append("")

    lines.append("## Avoid")
    floor_caveats = any(c.caveat for c in ranked)
    if not rejected:
        if floor_caveats:
            lines.append(
                "_No candidate was disqualified — BUT some candidates lacked enough trusted "
                "(fora / user-review) sources (see caveats above). A clean result here may mean "
                '"not enough trustworthy evidence to judge", NOT "confirmed safe"._'
            )
        else:
            lines.append(
                "_No candidate was disqualified: trusted sources (fora / user reviews) were "
                "searched and no disqualifying failure was corroborated._"
            )
    for cand in rejected:
        failures = [f for f in cand.findings if f.kind == "failure"]
        lines.append(f"### {cand.name}")
        for f in failures:
            crit = f" [{f.criterion}]" if f.criterion else ""
            lines.append(
                f"Avoid, because {f.corroboration_count} independent users report "
                f"<{f.claim}>{crit} (severity: {f.severity})."
            )
            if f.quote:
                lines.append(f"  > “{f.quote}”")
            lines.extend(_links([f]))
        if cand.caveat:
            lines.append(f"> ⚠ Caveat ({cand.caveat}): limited trusted sources.")
        lines.append("")

    if unevidenced:
        lines.append("## Insufficient credible evidence")
        lines.append(
            "_Considered, but supported only by marketing / affiliate pages, or too few "
            "independent sources — no verified user-experience (review / forum) "
            "corroboration met the floor, so not recommended:_"
        )
        for cand in unevidenced:
            suffix = f" — ⚠ {cand.caveat}" if cand.caveat else ""
            lines.append(f"- {cand.name}{suffix}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
