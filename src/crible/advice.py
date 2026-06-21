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

import re

from .models import Candidate, Criteria, Finding
from .skepticism import candidate_credible_strength

_CREDIBLE_TIERS = ("high", "medium")  # genuine lived experience (fora + user reviews)


def _addresses_disqualifier(finding: Finding, disqualifiers: list[str]) -> bool:
    """True if the finding's criterion is about one of the disqualifiers."""
    crit = finding.criterion.lower()
    ctokens = set(re.findall(r"\w+", crit))
    for d in disqualifiers:
        dl = d.lower()
        if (dl and dl in crit) or (crit and crit in dl):
            return True
        dtokens = {t for t in re.findall(r"\w+", dl) if len(t) > 3}
        if dtokens & ctokens:
            return True
    return False


def _disqualifier_proven(cand: Candidate, disqualifiers: list[str]) -> bool:
    """A recommendation needs credible lived-experience addressing the disqualifier.

    If the question has no disqualifier, this is vacuously satisfied.
    """
    if not disqualifiers:
        return True
    return any(
        f.kind == "support"
        and any(s.tier in _CREDIBLE_TIERS for s in f.sources)
        and _addresses_disqualifier(f, disqualifiers)
        for f in cand.findings
    )


def _has_credible_support(cand: Candidate, threshold: int) -> bool:
    """Recommendable when the candidate's credible support strength meets the floor —
    EITHER >= threshold distinct credible hosts, OR a single credible finding with
    >= threshold independent reviewer corroborations (so many user reviews on one
    marketplace count). Matches the evidence-mix floor."""
    return candidate_credible_strength(cand.findings) >= threshold


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
    proven = [
        c for c in ranked
        if not c.disqualified and _has_credible_support(c, corroboration_threshold)
    ]
    # Credible lived experience exists AND it addresses the disqualifier -> recommend.
    recommended = [c for c in proven if _disqualifier_proven(c, criteria.disqualifiers)]
    # Credible lived experience for the requirements, but NOT for the disqualifier.
    disq_unproven = [c for c in proven if not _disqualifier_proven(c, criteria.disqualifiers)]
    # Not disqualified, but only blog/echo-chamber context — not recommendable.
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
        n = candidate_credible_strength(cand.findings)
        lines.append(f"### {cand.name}")
        lines.append(
            f"This fits best, because it meets the requirements with "
            f"{n} independent user-experience corroborations (fora / user reviews)."
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

    if disq_unproven:
        disq = ", ".join(criteria.disqualifiers) or "the disqualifier"
        lines.append(f"## Requirements met — but “{disq}” NOT proven by lived experience")
        lines.append(
            "_These have credible user-experience support for the requirements, but no "
            f"forum/user-review evidence specifically about “{disq}” — so the key concern is "
            "unverified. Shown with their quotes; not recommended until the disqualifier is "
            "proven:_"
        )
        for cand in disq_unproven:
            caveat = f" — ⚠ {cand.caveat}" if cand.caveat else ""
            lines.append(f"### {cand.name}{caveat}")
            for f in [x for x in cand.findings if x.kind == "support"][:5]:
                crit = f" [{f.criterion}]" if f.criterion else ""
                lines.append(f"- {f.claim}{crit} ({f.corroboration_count} sources)")
                if f.quote:
                    lines.append(f"  > “{f.quote}”")
                lines.extend(_links([f]))
            lines.append("")

    if unevidenced:
        lines.append("## Context only — no lived-experience proof")
        lines.append(
            "_Considered. Context found (blogs / shops / manufacturer), shown below with "
            "quotes so you can judge — but NO genuine user-experience (forum / user-review) "
            "corroboration met the floor, so not recommended:_"
        )
        for cand in unevidenced:
            caveat = f" — ⚠ {cand.caveat}" if cand.caveat else ""
            lines.append(f"### {cand.name}{caveat}")
            for f in [x for x in cand.findings if x.kind == "support"][:4]:
                crit = f" [{f.criterion}]" if f.criterion else ""
                lines.append(f"- {f.claim}{crit}")
                if f.quote:
                    lines.append(f"  > “{f.quote}”")
                lines.extend(_links([f]))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
