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
        "topic": {"type": "string"},
        "positive": {"type": "array", "items": {"type": "string"}},
        "disqualifiers": {"type": "array", "items": {"type": "string"}},
        "budget": {"type": ["string", "null"]},
        "context": {"type": ["string", "null"]},
        # Is the question specific + measurable enough to research well?
        "specific_enough": {"type": "boolean"},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "topic",
        "positive",
        "disqualifiers",
        "budget",
        "context",
        "specific_enough",
        "clarifying_questions",
    ],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are the criteria-extraction lead of a bias-correcting product-research "
    "agent. Your job is to extract what the user actually needs, with NEGATIVE "
    "requirements (disqualifiers, e.g. 'no metallic taste') treated as first-class. "
    "Mainstream rankings ignore disqualifiers; you must not. "
    "Also set 'topic' to a short product-category phrase (e.g. 'travel coffee mug', "
    "'mechanical keyboard') used to find the topic's specialist community/forum.\n"
    "SPECIFICITY GATE: a good run needs a SPECIFIC, MEASURABLE question. Set "
    "specific_enough=false when the ask is too vague to research well — e.g. a bare "
    "'a safe trampoline' or 'a good laptop' with no concrete disqualifier, budget, "
    "size, or measurable requirement. When false, provide 2-4 short 'clarifying_"
    "questions' that would make it specific and measurable (budget? the exact failure "
    "to avoid? size/context? a measurable threshold?). When the question already has a "
    "clear category plus at least one concrete disqualifier or measurable constraint, "
    "set specific_enough=true and leave clarifying_questions empty."
)


def extract_criteria(client: LLMClient, question: str) -> Criteria:
    """Extract a structured Criteria object from the user's question."""
    data = client.extract(
        system=_SYSTEM,
        prompt=f"Question: {question}\n\nExtract the criteria and judge specificity.",
        schema=_SCHEMA,
    )
    return Criteria(
        question=question,
        topic=data.get("topic") or "",
        positive=list(data.get("positive") or []),
        disqualifiers=list(data.get("disqualifiers") or []),
        budget=data.get("budget"),
        context=data.get("context"),
        specific_enough=bool(data.get("specific_enough", True)),
        clarifying_questions=list(data.get("clarifying_questions") or []),
    )
