# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/orchestrator.py — the LEAD orchestrator (single-threaded MVP).
#
# Runs the staged orchestrator-worker flow (design D1):
#   1. criteria extraction (LEAD)         4. weighting + ranking (LEAD)
#   2. landscape + plan (LEAD, plan.json) 5. separate verification/citation pass
#   3. subagent threads (failure-hunting) 6. final advice
#
# Single-threaded by default. Subagents run sequentially unless parallelism is
# explicitly enabled in config (default OFF). Every stage writes to the audit
# trail; the run halts gracefully when the token ceiling is reached.
#
# Writes: through AuditLog (audit.jsonl, plan.json, advice.md)
# Idempotent: no (LLM calls; appends to the trail)
# Requires: LLMClient, TierList, AuditLog

from __future__ import annotations

from . import advice as advice_mod
from . import audit as ev
from . import criteria as criteria_mod
from . import ranking as ranking_mod
from . import verify as verify_mod
from .audit import AuditLog
from .config import Config
from .llm import CostCeilingReached, LLMClient
from .models import Candidate, Criteria, Finding, Source
from .skepticism import classify_sources, evaluate_finding
from .sources import TierList

_LANDSCAPE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "provenance": {"type": "string"},
                },
                "required": ["name", "provenance"],
                "additionalProperties": False,
            },
        },
        "plan": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["candidates", "plan"],
    "additionalProperties": False,
}

_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["failure", "support"]},
                    "claim": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["disqualifying", "minor", "unknown"],
                    },
                    "corroboration_count": {"type": "integer"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                    "skepticism_flags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "kind",
                    "claim",
                    "severity",
                    "corroboration_count",
                    "source_urls",
                    "skepticism_flags",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

_LANDSCAPE_SYSTEM = (
    "You are the landscape lead of a bias-correcting product-research agent. "
    "Build a BROAD candidate set that deliberately includes niche/long-tail "
    "options sourced from specialist communities — not only mainstream top-10 "
    "products. Popularity is not a virtue here. Then write a short research plan: "
    "one line per candidate describing how to hunt its failure modes in "
    "high-trust sources. Use web search to ground the candidate set."
)

_SUBAGENT_SYSTEM = (
    "You are a research subagent in a bias-correcting product agent. Investigate "
    "ONE candidate. Actively hunt its FAILURE MODES (especially the user's "
    "disqualifiers) in high-trust sources — specialist forums, communities, "
    "lived experience — not marketing or top-10 lists. Also note genuine support. "
    "Trust no single source: count INDEPENDENT corroborations (distinct accounts/"
    "sources, varied phrasing, spread over time); one enthusiastic post is not "
    "evidence. Flag manipulation signals (identical phrasing, very young accounts, "
    "sudden praise clusters). Distinguish 'not found (searched)' from 'confirmed "
    "absent'. Return condensed findings with the source URLs you actually used."
)


class Orchestrator:
    """Drives the single-threaded research run end to end."""

    def __init__(self, config: Config, log: AuditLog) -> None:
        self.config = config
        self.log = log
        self.client = LLMClient(config)
        self.tier_list = TierList.load(config.source_tiers_path)

    # ---- stage 1: criteria ------------------------------------------------

    def extract_criteria(self, question: str) -> Criteria:
        criteria = criteria_mod.extract_criteria(self.client, question)
        self.log.log(ev.EVENT_CRITERIA, **criteria.to_dict())
        return criteria

    # ---- stage 2: landscape + plan ---------------------------------------

    def build_landscape(self, criteria: Criteria) -> list[Candidate]:
        prompt = (
            f"Question: {criteria.question}\n"
            f"Requirements: {criteria.positive}\n"
            f"Disqualifiers: {criteria.disqualifiers}\n"
            f"Budget: {criteria.budget}\nContext: {criteria.context}\n\n"
            "Build the candidate landscape and the research plan."
        )
        research = self.client.research(_LANDSCAPE_SYSTEM, prompt)
        for q in research.queries:
            self.log.log(ev.EVENT_QUERY, stage="landscape", query=q)
        data = self.client.extract(
            system=_LANDSCAPE_SYSTEM,
            prompt=f"From this research, return the candidate set and plan:\n\n{research.text}",
            schema=_LANDSCAPE_SCHEMA,
        )
        candidates = [
            Candidate(name=c["name"], provenance=c.get("provenance", ""))
            for c in data.get("candidates", [])
        ]
        # Cap candidate count to the subagent cap (effort scales to complexity).
        if len(candidates) > self.config.max_subagents:
            self.log.log(
                ev.EVENT_NOTE,
                stage="landscape",
                note="candidate set capped to max_subagents",
                cap=self.config.max_subagents,
                dropped=len(candidates) - self.config.max_subagents,
            )
            candidates = candidates[: self.config.max_subagents]

        plan = {
            "candidates": [c.to_dict() for c in candidates],
            "plan": data.get("plan", []),
        }
        self.log.write_json("plan.json", plan)  # external memory (design D4/OQ4)
        self.log.log(ev.EVENT_PLAN, candidate_count=len(candidates), steps=data.get("plan", []))
        for c in candidates:
            self.log.log(ev.EVENT_NOTE, stage="candidate", name=c.name, provenance=c.provenance)
        return candidates

    # ---- stage 3: subagent threads (failure-hunting) ---------------------

    def investigate(self, criteria: Criteria, candidate: Candidate) -> None:
        prompt = (
            f"Candidate: {candidate.name}\n"
            f"User requirements: {criteria.positive}\n"
            f"Disqualifiers to hunt: {criteria.disqualifiers}\n"
            f"Context: {criteria.context}\n\n"
            "Investigate this candidate and return condensed findings."
        )
        research = self.client.research(_SUBAGENT_SYSTEM, prompt)
        for q in research.queries:
            self.log.log(ev.EVENT_QUERY, stage="subagent", candidate=candidate.name, query=q)
        for src in research.sources:
            self.log.log(
                ev.EVENT_SOURCE_VISITED, candidate=candidate.name, url=src.url, title=src.title
            )

        data = self.client.extract(
            system=_SUBAGENT_SYSTEM,
            prompt=(
                f"From this investigation of {candidate.name}, return the findings. "
                f"Only cite URLs that appear in the research:\n\n{research.text}"
            ),
            schema=_FINDINGS_SCHEMA,
        )
        for raw in data.get("findings", []):
            sources = [Source(url=u) for u in raw.get("source_urls", [])]
            sources = classify_sources(self.tier_list, sources)
            for s in sources:
                self.log.log(
                    ev.EVENT_CLASSIFICATION,
                    candidate=candidate.name,
                    url=s.url,
                    tier=s.tier,
                    rule=s.tier_rule,
                )
            finding = Finding(
                candidate=candidate.name,
                kind=raw.get("kind", "support"),
                claim=raw.get("claim", ""),
                severity=raw.get("severity", "unknown"),
                sources=sources,
                corroboration_count=int(raw.get("corroboration_count", 0)),
                skepticism_flags=list(raw.get("skepticism_flags", [])),
            )
            fired = evaluate_finding(finding, self.config.corroboration_threshold)
            for rule in fired:
                self.log.log(
                    ev.EVENT_SKEPTICISM_RULE,
                    candidate=candidate.name,
                    rule=rule,
                    claim=finding.claim,
                )
            self.log.log(
                ev.EVENT_CORROBORATION,
                candidate=candidate.name,
                claim=finding.claim,
                independent_count=finding.corroboration_count,
            )
            self.log.log(ev.EVENT_FINDING, **finding.to_dict())
            candidate.findings.append(finding)

    # ---- run --------------------------------------------------------------

    def run(self, question: str) -> tuple[Criteria, list[Candidate], str]:
        self.log.log(ev.EVENT_RUN_SETTINGS, **self.config.effective_settings())

        criteria = self.extract_criteria(question)
        if criteria.clarification_needed:
            # Disqualifier-first: surface the question instead of guessing.
            self.log.log(
                ev.EVENT_NOTE,
                stage="criteria",
                clarification_needed=criteria.clarification_needed,
            )

        candidates: list[Candidate] = []
        try:
            candidates = self.build_landscape(criteria)
            # Single-threaded by default (parallelism is an explicit opt-in).
            for cand in candidates:
                self.client.check_ceiling()
                self.investigate(criteria, cand)
        except CostCeilingReached as exc:
            self.log.log(
                ev.EVENT_STOP,
                reason="cost_ceiling",
                detail=str(exc),
                tokens_used=self.client.tokens_used,
            )

        ranked = ranking_mod.rank(candidates, self.config.corroboration_threshold)
        for cand in ranked:
            self.log.log(
                ev.EVENT_SCORE,
                candidate=cand.name,
                score=cand.score,
                disqualified=cand.disqualified,
                reason=cand.reason,
            )

        verify_mod.verify(ranked, self.log)
        document = advice_mod.render(criteria, ranked)
        self.log.write_json("advice.md", document)
        self.log.log(
            ev.EVENT_COST, stage="final", tokens_used=self.client.tokens_used,
            ceiling=self.config.token_ceiling,
        )
        return criteria, ranked, document
