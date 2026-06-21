# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/verify.py — the separate verification/citation pass (design D1/D7).
#
# Runs after ranking, as its own stage. It drops any finding that has no source
# ("no grounding = no claim") and emits the grounding portion of the audit trail
# as a by-product, so the record cannot drift from the decision it documents.
#
# Writes: through the AuditLog (grounding events)
# Idempotent: yes (re-running re-verifies the same findings)
# Requires: stdlib + AuditLog + models

from __future__ import annotations

from . import audit as audit_events
from .audit import AuditLog
from .models import Candidate


def verify(candidates: list[Candidate], log: AuditLog) -> list[Candidate]:
    """Drop ungrounded findings and log the grounding for every surviving claim.

    A finding survives only if it carries at least one source. Findings without
    grounding are removed before the advice is rendered.
    """
    for cand in candidates:
        kept = []
        for f in cand.findings:
            if not f.sources:
                log.log(
                    audit_events.EVENT_NOTE,
                    stage="verification",
                    candidate=cand.name,
                    dropped_claim=f.claim,
                    reason="no grounding (no sources)",
                )
                continue
            log.log(
                audit_events.EVENT_DECISION,
                stage="verification",
                candidate=cand.name,
                kind=f.kind,
                claim=f.claim,
                severity=f.severity,
                corroboration_count=f.corroboration_count,
                sources=[s.to_dict() for s in f.sources],
                grounded=True,
            )
            kept.append(f)
        cand.findings = kept
    return candidates
