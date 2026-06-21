# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/criteria.py — LEAD criteria extraction (disqualifier-first).
#
# Derives positive requirements, NEGATIVE requirements (disqualifiers), budget
# and context from the question, and flags when a likely disqualifier is missing
# so the caller can ask back (design D6). Uses the structured-output path so the
# shape is deterministic and auditable.
#
# Writes: read-only
# Idempotent: no (one LLM call)
# Requires: LLMClient

from __future__ import annotations

from .llm import LLMClient
from .models import Criteria

_SCHEMA = {
    "type": "object",
    "properties": {
        "positive": {"type": "array", "items": {"type": "string"}},
        "disqualifiers": {"type": "array", "items": {"type": "string"}},
        "budget": {"type": ["string", "null"]},
        "context": {"type": ["string", "null"]},
        "missing_disqualifier_question": {"type": ["string", "null"]},
    },
    "required": [
        "positive",
        "disqualifiers",
        "budget",
        "context",
        "missing_disqualifier_question",
    ],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are the criteria-extraction lead of a bias-correcting product-research "
    "agent. Your job is to extract what the user actually needs, with NEGATIVE "
    "requirements (disqualifiers, e.g. 'no metallic taste') treated as first-class. "
    "Mainstream rankings ignore disqualifiers; you must not. If the product "
    "category has a well-known failure mode the user did not mention, set "
    "missing_disqualifier_question to a single clarifying question; otherwise null. "
    "Scale effort to the question: do not invent requirements for a trivial ask."
)


def extract_criteria(client: LLMClient, question: str) -> Criteria:
    """Extract a structured Criteria object from the user's question."""
    data = client.extract(
        system=_SYSTEM,
        prompt=f"Question: {question}\n\nExtract the criteria.",
        schema=_SCHEMA,
    )
    return Criteria(
        question=question,
        positive=list(data.get("positive") or []),
        disqualifiers=list(data.get("disqualifiers") or []),
        budget=data.get("budget"),
        context=data.get("context"),
        clarification_needed=data.get("missing_disqualifier_question"),
    )
