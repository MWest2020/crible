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
from .links import LinkChecker
from .llm import CostCeilingReached, LLMClient
from .models import Candidate, Criteria, Finding, Source
from .skepticism import classify_sources, count_independent, evaluate_finding
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
                    "quote": {"type": "string"},
                    "criterion": {"type": "string"},
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
                    "quote",
                    "criterion",
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
    "ONE candidate against the user's criteria.\n"
    "PRIORITY: the user's DISQUALIFIERS are the point. Spend most effort finding "
    "empirical evidence about the disqualifier(s) specifically (e.g. for 'metallic "
    "taste', hunt taste/flavour reports — NOT temperature/insulation). Do not pad "
    "with generic positive specs that the user did not ask about; a finding that "
    "does not address a stated requirement or disqualifier is noise — drop it. Tag "
    "every finding with the exact criterion it addresses in the 'criterion' field.\n"
    "EVIDENCE HIERARCHY (prefer in this order): substantive discussion / empirical "
    "evidence (someone actually tested it) > user reviews (lived experience) > "
    "blogs / marketing. BLOGS ARE AN ECHO CHAMBER AND DO NOT COUNT: ten blogs "
    "repeating the same affiliate line is not corroboration, it is one claim "
    "copied ten times — they will be discarded. Spend your searches on real user "
    "reviews and forum threads: query marketplace review pages (e.g. "
    "'<candidate> amazon reviews', the '.../product-reviews/...' page), and "
    "communities ('<candidate> <disqualifier> reddit', '<candidate> <disqualifier> "
    "forum', 'site:reddit.com <candidate> <disqualifier>'). Only cite a finding if "
    "you found it in user reviews or fora; do not cite manufacturer pages, "
    "top-10 lists or SEO blogs as your evidence.\n"
    "Trust no single source: count INDEPENDENT corroborations (distinct accounts/"
    "sources, varied phrasing, spread over time); one enthusiastic post is not "
    "evidence. Flag manipulation signals (identical phrasing, very young accounts, "
    "sudden praise clusters). Distinguish 'not found (searched)' from 'confirmed "
    "absent'. Return condensed findings with the source URLs you actually used.\n"
    "EVERY finding MUST include a 'quote': a SHORT VERBATIM excerpt (the user's own "
    "words, <=240 chars) from one of the cited sources that shows the lived "
    "experience behind the claim. Copy it exactly — do not paraphrase or invent. If "
    "you cannot quote a real source, drop the finding."
)


class Orchestrator:
    """Drives the single-threaded research run end to end."""

    def __init__(self, config: Config, log: AuditLog) -> None:
        self.config = config
        self.log = log
        self.client = LLMClient(config)
        self.tier_list = TierList.load(config.source_tiers_path)
        # Steering domain lists, derived once from the seed tier list (design D4).
        if config.domain_steering_enabled:
            # Exclude domains the provider's crawler can't reach (e.g. reddit) —
            # listing them in allowed_domains 400s the whole request.
            noncrawlable = set(config.noncrawlable_search_domains)
            self._allow_domains = [
                d for d in self.tier_list.allow_domains() if d not in noncrawlable
            ]
            self._block_domains = sorted(
                set(self.tier_list.block_domains()) | set(config.blocked_search_domains)
            )
        else:
            self._allow_domains = []
            self._block_domains = []
        self._links = LinkChecker(
            timeout=config.link_check_timeout, enabled=config.verify_links
        )

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

    def _augmented_queries(self, criteria: Criteria, candidate: Candidate) -> list[str]:
        """Deterministic forum/review-targeted queries from the seed templates."""
        disq = (
            criteria.disqualifiers[0]
            if criteria.disqualifiers
            else (criteria.positive[0] if criteria.positive else "review")
        )
        queries = [
            t.format(candidate=candidate.name, disqualifier=disq)
            for t in self.config.query_templates
        ]
        # site: queries for the first couple of listed specialist fora (steering hint).
        for forum in self._allow_domains[:2]:
            queries.append(f"site:{forum} {candidate.name} {disq}")
        return queries

    def _search_pass(
        self,
        candidate: Candidate,
        prompt: str,
        label: str,
        templates: list[str],
        *,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ):
        """One steered research pass; logs its domains, templates and queries."""
        research = self.client.research(
            _SUBAGENT_SYSTEM, prompt,
            allowed_domains=allowed_domains, blocked_domains=blocked_domains,
        )
        self.log.log(
            ev.EVENT_SEARCH_DOMAINS, candidate=candidate.name, pass_=label,
            allowed=research.allowed_domains or [], blocked=research.blocked_domains or [],
            degraded=research.degraded, degraded_reason=research.degraded_reason,
        )
        self.log.log(
            ev.EVENT_QUERY_TEMPLATES, candidate=candidate.name, pass_=label, templates=templates
        )
        for q in research.queries:
            self.log.log(ev.EVENT_QUERY, stage=label, candidate=candidate.name, query=q)
        for src in research.sources:
            self.log.log(
                ev.EVENT_SOURCE_VISITED, candidate=candidate.name, url=src.url, title=src.title
            )
        return research

    def _extract_findings(
        self, criteria: Criteria, candidate: Candidate, text: str, visited: list[str]
    ) -> None:
        """Extract findings grounded ONLY in the visited URLs; classify + evaluate."""
        if not text.strip():
            return
        visited_set = set(visited)
        visited_block = "\n".join(visited) if visited else "(no sources were retrieved)"
        data = self.client.extract(
            system=_SUBAGENT_SYSTEM,
            prompt=(
                f"From this investigation of {candidate.name}, return the findings.\n\n"
                f"Sources you actually visited (cite source_urls ONLY from this list, "
                f"verbatim):\n{visited_block}\n\nResearch notes:\n{text}"
            ),
            schema=_FINDINGS_SCHEMA,
        )
        for raw in data.get("findings", []):
            urls = [u for u in raw.get("source_urls", []) if u in visited_set]
            sources = classify_sources(self.tier_list, [Source(url=u) for u in urls])
            # Drop dead links — a broken citation is a no-go (no LIVE grounding = no claim).
            live: list[Source] = []
            for s in sources:
                if self._links.is_live(s.url):
                    live.append(s)
                    self.log.log(
                        ev.EVENT_CLASSIFICATION, candidate=candidate.name,
                        url=s.url, tier=s.tier, rule=s.tier_rule,
                    )
                else:
                    self.log.log(
                        ev.EVENT_NOTE, stage="link-check", candidate=candidate.name,
                        dropped_url=s.url, reason="dead link (404/410/unreachable)",
                    )
            sources = live
            if not sources:
                # All citations dead -> the claim is ungrounded; drop it.
                self.log.log(
                    ev.EVENT_NOTE, stage="link-check", candidate=candidate.name,
                    dropped_claim=raw.get("claim", ""), reason="no live sources",
                )
                continue
            reported = int(raw.get("corroboration_count", 0))
            finding = Finding(
                candidate=candidate.name,
                kind=raw.get("kind", "support"),
                claim=raw.get("claim", ""),
                quote=raw.get("quote", ""),
                criterion=raw.get("criterion", ""),
                severity=raw.get("severity", "unknown"),
                sources=sources,
                corroboration_count=reported,
                skepticism_flags=list(raw.get("skepticism_flags", [])),
            )
            for rule in evaluate_finding(finding, self.config.corroboration_threshold):
                self.log.log(
                    ev.EVENT_SKEPTICISM_RULE, candidate=candidate.name,
                    rule=rule, claim=finding.claim,
                )
            self.log.log(
                ev.EVENT_CORROBORATION, candidate=candidate.name, claim=finding.claim,
                reported_count=reported, credible_count=finding.corroboration_count,
            )
            self.log.log(ev.EVENT_SOURCE_TIER_MIX, candidate=candidate.name, claim=finding.claim,
                         **self._tier_mix(finding))
            self.log.log(ev.EVENT_FINDING, **finding.to_dict())
            candidate.findings.append(finding)

    def _tier_mix(self, finding: Finding) -> dict:
        counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        for s in finding.sources:
            counts[s.tier] = counts.get(s.tier, 0) + 1
        credible = count_independent(finding.sources)  # distinct high+medium hosts
        return {
            "tiers": counts,
            "credible_hosts": credible,
            "floor": self.config.evidence_mix_floor,
            "meets_floor": credible >= self.config.evidence_mix_floor,
        }

    def _candidate_credible_hosts(self, candidate: Candidate) -> int:
        all_sources = [s for f in candidate.findings for s in f.sources]
        return count_independent(all_sources)

    def investigate(self, criteria: Criteria, candidate: Candidate) -> None:
        templates = self._augmented_queries(criteria, candidate)
        tmpl_block = "\n".join(f"- {q}" for q in templates)
        base = (
            f"Candidate: {candidate.name}\n"
            f"User requirements: {criteria.positive}\n"
            f"Disqualifiers to hunt: {criteria.disqualifiers}\n"
            f"Context: {criteria.context}\n\n"
            f"Run web searches including these, then return condensed findings:\n{tmpl_block}\n"
        )
        # High-trust pass (allow-list of specialist fora + review platforms) first,
        # then the open pass (block known affiliate/blog domains).
        merged_sources: list[Source] = []
        text_parts: list[str] = []
        passes = [
            ("high-trust", {"allowed_domains": self._allow_domains or None}),
            ("open", {"blocked_domains": self._block_domains or None}),
        ]
        for label, steer in passes:
            research = self._search_pass(candidate, base, label, templates, **steer)
            merged_sources.extend(research.sources)
            if research.text:
                text_parts.append(research.text)

        visited = list(dict.fromkeys(s.url for s in merged_sources))
        self._extract_findings(criteria, candidate, "\n".join(text_parts), visited)

        # Evidence-mix floor: bounded one-shot high-trust re-search on breach.
        before = self._candidate_credible_hosts(candidate)
        self.log.log(
            ev.EVENT_FLOOR_CHECK, candidate=candidate.name, stage="initial",
            credible_hosts=before, floor=self.config.evidence_mix_floor,
            meets_floor=before >= self.config.evidence_mix_floor,
        )
        if before < self.config.evidence_mix_floor and self.config.evidence_research_extra_passes:
            research = self._search_pass(
                candidate, base + "\nFocus ONLY on specialist forums and user reviews.",
                "high-trust-research", templates, allowed_domains=self._allow_domains or None,
            )
            visited2 = list(dict.fromkeys(s.url for s in research.sources))
            self._extract_findings(criteria, candidate, research.text, visited2)
            after = self._candidate_credible_hosts(candidate)
            self.log.log(
                ev.EVENT_FLOOR_CHECK, candidate=candidate.name, stage="after-research",
                credible_hosts=after, floor=self.config.evidence_mix_floor,
                meets_floor=after >= self.config.evidence_mix_floor,
            )
            before = after

        if before < self.config.evidence_mix_floor:
            candidate.caveat = "evidence-mix-floor-not-met"
            self.log.log(
                ev.EVENT_FLOOR_NOT_MET, candidate=candidate.name,
                credible_hosts=before, floor=self.config.evidence_mix_floor,
            )

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
            # Fail-fast budget guard: estimate the per-subagent cost from actuals
            # (seeded by the landscape cost) and DON'T start a subagent we can't
            # fund — so a token-heavy model aborts early with guidance instead of
            # grinding to the ceiling and producing nothing.
            estimate = max(self.client.tokens_used, 1)  # landscape cost as first proxy
            done = 0
            for cand in candidates:
                remaining = self.config.token_ceiling - self.client.tokens_used
                if remaining < estimate:
                    self.log.log(
                        ev.EVENT_STOP,
                        reason="budget_too_low_for_subagent",
                        detail=(
                            f"~{estimate} tokens needed per candidate but only {remaining} "
                            f"left of {self.config.token_ceiling}; model '{self.config.model}' "
                            f"is too token-heavy for this ceiling. Raise --token-ceiling or use "
                            f"a cheaper model (e.g. --model claude-haiku-4-5)."
                        ),
                        tokens_used=self.client.tokens_used,
                        candidates_done=done,
                        candidates_total=len(candidates),
                    )
                    break
                before = self.client.tokens_used
                self.investigate(criteria, cand)
                spent = self.client.tokens_used - before
                if spent > 0:
                    estimate = spent  # refine from the most recent actual
                done += 1
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
        document = advice_mod.render(criteria, ranked, self.config.corroboration_threshold)
        self.log.write_json("advice.md", document)
        self.log.log(
            ev.EVENT_COST, stage="final", tokens_used=self.client.tokens_used,
            ceiling=self.config.token_ceiling,
        )
        self._links.close()
        return criteria, ranked, document
