# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/ranking.py — transparent ranking by source-trust x corroboration
# x failure-severity (design D5).
#
# The score is an explicit function of three logged inputs only. No commercial
# signal (affiliate/commission/sponsorship) and no popularity/volume signal is
# an input — that neutrality is the hard design principle (kernprincipe 6) and a
# spec constraint, not a tuning choice. A disqualifying failure mode that clears
# the corroboration threshold removes the candidate from the recommendation set.
#
# Writes: read-only
# Idempotent: yes
# Requires: stdlib only

from __future__ import annotations

from .models import Candidate, Finding

# Tier weights. PROOF tiers (genuine lived experience): high (fora) and medium
# (marketplace / review-platform user reviews). Context tiers carry almost no
# weight — unknown (review blogs / unlisted) 0.1, low (affiliate / manufacturer)
# 0.0 — so they never drive a recommendation, only appear as shown context.
_TIER_WEIGHT = {"high": 1.0, "medium": 0.6, "unknown": 0.1, "low": 0.0}
_SEVERITY_WEIGHT = {"disqualifying": 1.0, "minor": 0.4, "unknown": 0.4}


def _support_weight(finding: Finding) -> float:
    trust = max((_TIER_WEIGHT.get(s.tier, 0.1) for s in finding.sources), default=0.0)
    return trust * finding.corroboration_count


def _failure_penalty(finding: Finding) -> float:
    trust = max((_TIER_WEIGHT.get(s.tier, 0.1) for s in finding.sources), default=0.0)
    severity = _SEVERITY_WEIGHT.get(finding.severity, 0.4)
    return trust * finding.corroboration_count * severity


def rank(candidates: list[Candidate], corroboration_threshold: int) -> list[Candidate]:
    """Score and order candidates; disqualify on corroborated disqualifying failures.

    Returns the list sorted best-first. Mutates each candidate's score,
    disqualified flag and reason so the audit trail can record all three inputs.
    """
    for cand in candidates:
        support = 0.0
        penalty = 0.0
        disqualifying: list[Finding] = []
        for f in cand.findings:
            if f.kind == "support":
                support += _support_weight(f)
            elif f.kind == "failure":
                penalty += _failure_penalty(f)
                if (
                    f.severity == "disqualifying"
                    and f.corroboration_count >= corroboration_threshold
                    and any(s.tier == "high" for s in f.sources)
                ):
                    disqualifying.append(f)

        cand.score = support - penalty
        if disqualifying:
            cand.disqualified = True
            modes = "; ".join(f.claim for f in disqualifying)
            cand.reason = f"disqualified: {modes}"
        else:
            cand.reason = f"score {cand.score:.2f} (support {support:.2f} - failures {penalty:.2f})"

    # Qualified candidates first (by score desc), then disqualified ones.
    return sorted(candidates, key=lambda c: (c.disqualified, -c.score))
