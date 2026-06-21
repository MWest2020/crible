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

from .models import Candidate, Criteria, Finding


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


def render(criteria: Criteria, ranked: list[Candidate]) -> str:
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

    recommended = [c for c in ranked if not c.disqualified and c.findings]
    rejected = [c for c in ranked if c.disqualified]
    unevidenced = [c for c in ranked if not c.disqualified and not c.findings]

    lines.append("## Recommended")
    if not recommended:
        lines.append("_No candidate has sufficient grounded support to recommend._")
    for cand in recommended:
        supports = [f for f in cand.findings if f.kind == "support"]
        n = sum(f.corroboration_count for f in supports) or len(supports)
        lines.append(f"### {cand.name}")
        lines.append(f"This fits best, because it meets the requirements ({n} sources).")
        lines.append(f"_Reason:_ {cand.reason}")
        for f in supports:
            lines.append(f"- {f.claim} ({f.corroboration_count} independent sources)")
            lines.extend(_links([f]))
        lines.append("")

    lines.append("## Avoid")
    if not rejected:
        lines.append("_No candidate was disqualified._")
    for cand in rejected:
        failures = [f for f in cand.findings if f.kind == "failure"]
        lines.append(f"### {cand.name}")
        for f in failures:
            lines.append(
                f"Avoid, because {f.corroboration_count} independent users report "
                f"<{f.claim}> (severity: {f.severity})."
            )
            lines.extend(_links([f]))
        lines.append("")

    if unevidenced:
        lines.append("## Insufficient evidence")
        lines.append("_Considered, but no grounded claim survived verification:_")
        for cand in unevidenced:
            lines.append(f"- {cand.name}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
