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

import re

from . import advice as advice_mod
from . import audit as ev
from . import criteria as criteria_mod
from . import ranking as ranking_mod
from . import verify as verify_mod
from .audit import AuditLog
from .config import Config
from .fetch import ContentFetcher, quote_matches
from .links import LinkChecker
from .llm import CostCeilingReached, LLMClient
from .models import Candidate, Criteria, Finding, Source
from .skepticism import (
    candidate_credible_strength,
    classify_sources,
    count_independent,
    evaluate_finding,
)
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
    "products. Popularity is not a virtue here. "
    "CRITICAL: each candidate MUST be a SPECIFIC, buyable product — exact brand + "
    "model (e.g. 'Zojirushi SM-SF48', 'Fellow Carter Move Mug'), NOT a category or "
    "material class (NOT 'glass-lined thermoses' or '316L stainless thermoses'). "
    "If you only know a category, name the specific models within it. "
    "Then write a short research plan: one line per candidate describing how to hunt "
    "its failure modes in high-trust sources. Use web search to ground the set."
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
    "communities. Find the TOPIC'S OWN specialist community (e.g. a coffee or gear "
    "forum) — do not default to reddit alone; reddit is one option among the topic's "
    "real communities. Try 'best <topic> forum', '<candidate> <disqualifier> forum', "
    "'<candidate> <disqualifier> reddit'. Only cite a finding if "
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
        self._fetcher = ContentFetcher(
            max_chars=config.max_fetch_chars, enabled=config.fetch_enabled
        )
        self._candidate_brands: set[str] = set()  # set after landscape, for attribution

    # ---- stage 1: criteria ------------------------------------------------

    def extract_criteria(self, question: str) -> Criteria:
        criteria = criteria_mod.extract_criteria(self.client, question)
        self.log.log(ev.EVENT_CRITERIA, **criteria.to_dict())
        return criteria

    # ---- stage 2: landscape + plan ---------------------------------------

    def _landscape_pages(self, criteria: Criteria):
        """Search the topic's communities/reviews and fetch the top pages, so
        candidates can be DERIVED from what real users discuss (not invented)."""
        topic = criteria.topic or criteria.question
        disq = criteria.disqualifiers[0] if criteria.disqualifiers else ""
        queries = [
            f"best {topic} reddit",
            f"what {topic} do you recommend forum",
            f"best {topic} {disq}".strip(),
            f"{topic} {disq} site:reddit.com".strip(),
            f"{topic} owners review experience",
        ]
        qblock = "\n".join(f"- {q}" for q in queries)
        prompt = (
            f"Find which SPECIFIC products (brand + model) real users discuss and recommend "
            f"for: {criteria.question}\nTopic: {topic}\n\n"
            f"Run web searches including these, favouring forums and user reviews:\n{qblock}"
        )
        merged: list[Source] = []
        passes = [
            ("landscape-high-trust", {"allowed_domains": self._allow_domains or None}),
            ("landscape-open", {"blocked_domains": self._block_domains or None}),
        ]
        for label, steer in passes:
            research = self.client.research(_LANDSCAPE_SYSTEM, prompt, **steer)
            self.log.log(
                ev.EVENT_SEARCH_DOMAINS, stage="landscape", pass_=label,
                allowed=research.allowed_domains or [], blocked=research.blocked_domains or [],
                degraded=research.degraded, degraded_reason=research.degraded_reason,
            )
            for q in research.queries:
                self.log.log(ev.EVENT_QUERY, stage="landscape", query=q)
            merged.extend(research.sources)
        uniq, seen = [], set()
        for s in classify_sources(self.tier_list, merged):
            if s.url not in seen:
                seen.add(s.url)
                uniq.append(s)
        uniq.sort(key=lambda s: self._FETCH_RANK.get(s.tier, 2))
        pages = []
        for s in uniq[: self.config.max_fetch_pages_per_finding]:
            text = self._fetcher.fetch(s.url)
            self.log.log(
                ev.EVENT_FETCH, stage="landscape", url=s.url, tier=s.tier,
                ok=bool(text), chars=len(text or ""),
            )
            if text:
                pages.append((s, text))
        return pages

    def build_landscape(self, criteria: Criteria) -> list[Candidate]:
        pages = self._landscape_pages(criteria) if self.config.fetch_enabled else []
        if pages:
            blocks = [
                f"[SOURCE {i}] {s.url} (trust: {s.tier})\n{t[: self.config.fetch_prompt_chars]}"
                for i, (s, t) in enumerate(pages, 1)
            ]
            prompt = (
                "From the community / review texts below, extract the SPECIFIC products "
                "(exact brand + model) that real users actually discuss or recommend for the "
                "need; set each one's provenance to the source URL where it was discussed. "
                "If fewer than 5 such products appear, ALSO add well-known, widely-available "
                "specific products (brand + model) for this need (provenance: 'well-known') so "
                "there are enough candidates. Avoid obscure or unbranded items. Add a one-line "
                "research plan per candidate.\n"
                f"Need: {criteria.question}\nRequirements: {criteria.positive}\n"
                f"Disqualifiers: {criteria.disqualifiers}\n\n" + "\n\n".join(blocks)
            )
        else:
            prompt = (
                f"Question: {criteria.question}\nRequirements: {criteria.positive}\n"
                f"Disqualifiers: {criteria.disqualifiers}\n\n"
                "Build the candidate set (SPECIFIC products) and a short research plan."
            )
        data = self.client.extract(
            system=_LANDSCAPE_SYSTEM, prompt=prompt, schema=_LANDSCAPE_SCHEMA
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
        topic = criteria.topic or criteria.question
        queries = [
            t.format(candidate=candidate.name, disqualifier=disq, topic=topic)
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

    _FETCH_RANK = {"high": 0, "medium": 1, "unknown": 2, "low": 3}

    @staticmethod
    def _brand_token(name: str) -> str:
        """First distinctive word of a candidate name (the brand), for attribution."""
        for tok in re.findall(r"\w+", name):
            if len(tok) > 2 and not tok.isdigit():
                return tok.lower()
        return ""

    def _ingest(self, criteria, candidate, sources, search_text):
        """Turn search results into grounded findings.

        Fetch ON (default): pre-fetch the cited pages (shops, reviews, fora) and
        extract findings FROM the real page text, quoting verbatim — so user
        experiences on shop sites and forum threads survive verification instead of
        being dropped. Fetch OFF: extract from the search prose, ground by link-liveness.
        """
        if self.config.fetch_enabled:
            pages = self._fetch_pages(candidate, sources)
            self._extract_from_pages(criteria, candidate, pages)
        else:
            visited = list(dict.fromkeys(s.url for s in sources))
            self._extract_findings(criteria, candidate, search_text, visited)

    def _fetch_pages(self, candidate, sources):
        """Fetch top cited pages (credible first, but include shops/reviews).

        Returns [(Source, full_text)]; a page that won't fetch is dropped as dead.
        """
        uniq, seen = [], set()
        for s in classify_sources(self.tier_list, sources):
            if s.url not in seen:
                seen.add(s.url)
                uniq.append(s)
        uniq.sort(key=lambda s: self._FETCH_RANK.get(s.tier, 2))
        pages = []
        for s in uniq[: self.config.max_fetch_pages_per_finding]:
            text = self._fetcher.fetch(s.url)
            self.log.log(
                ev.EVENT_FETCH, candidate=candidate.name, url=s.url,
                tier=s.tier, ok=bool(text), chars=len(text or ""),
            )
            if text:
                pages.append((s, text))
            else:
                self.log.log(
                    ev.EVENT_NOTE, stage="fetch", candidate=candidate.name,
                    dropped_url=s.url, reason="dead/unfetchable",
                )
        return pages

    def _extract_from_pages(self, criteria, candidate, pages):
        """Extract findings FROM fetched page text; the quote must be verbatim from it."""
        if not pages:
            return
        text_by_url = {s.url: text for s, text in pages}
        blocks = [
            f"[SOURCE {i}] {s.url} (trust: {s.tier})\n{text[: self.config.fetch_prompt_chars]}"
            for i, (s, text) in enumerate(pages, 1)
        ]
        prompt = (
            f"Investigate {candidate.name} against the user's criteria using ONLY the "
            f"source texts below.\nRequirements: {criteria.positive}\n"
            f"Disqualifiers to hunt: {criteria.disqualifiers}\n\n"
            "PROOF means genuine USER EXPERIENCE — a forum/community post or a real user "
            "review on a shop/review platform. Manufacturer pages and review blogs are "
            "context, not proof. Prefer quotes where a user speaks from experience. "
            f"Each finding MUST be specifically about {candidate.name}: the quote must be "
            f"about THIS product. If a forum thread discusses several products, do NOT "
            f"attribute a quote about a different product to {candidate.name}. "
            "For each finding, 'quote' MUST be copied VERBATIM from the text of the source "
            "you cite, and 'source_urls' MUST contain that source's URL exactly. Set "
            "'corroboration_count' to the number of DISTINCT users/reviews/posts you saw "
            "supporting that finding (if several reviewers say the same thing, count them) "
            "and quote one representative. Use only the sources listed below.\n\n"
            + "\n\n".join(blocks)
        )
        data = self.client.extract(
            system=_SUBAGENT_SYSTEM, prompt=prompt, schema=_FINDINGS_SCHEMA
        )
        for raw in data.get("findings", []):
            urls = [u for u in raw.get("source_urls", []) if u in text_by_url]
            quote, claim = raw.get("quote", ""), raw.get("claim", "")
            if not urls:
                self.log.log(
                    ev.EVENT_NOTE, stage="extract", candidate=candidate.name,
                    dropped_claim=claim, reason="cited a source not in the provided list",
                )
                continue
            matched, best = False, 0.0
            for u in urls:
                ok, score = quote_matches(quote, text_by_url[u], self.config.quote_match_ratio)
                best = max(best, score)
                if ok:
                    matched = True
                    break
            self.log.log(
                ev.EVENT_QUOTE_CHECK, candidate=candidate.name, claim=claim,
                matched=matched, score=round(best, 2), ratio=self.config.quote_match_ratio,
            )
            if not matched:
                self.log.log(
                    ev.EVENT_NOTE, stage="quote-check", candidate=candidate.name,
                    dropped_claim=claim, reason="quote not in cited page text",
                )
                continue
            # Attribution guard: drop only if the quote names a DIFFERENT candidate's
            # brand and not this one (a quote about another product in a multi-product
            # thread). Generic reviews that name no brand are kept — most real reviews
            # on a product's own page don't repeat the brand.
            ql = quote.lower()
            this_brand = self._brand_token(candidate.name)
            others = {b for b in self._candidate_brands if b and b != this_brand}
            names_other = any(b in ql for b in others)
            names_this = bool(this_brand) and this_brand in ql
            if names_other and not names_this:
                self.log.log(
                    ev.EVENT_NOTE, stage="attribution", candidate=candidate.name,
                    dropped_claim=claim, reason="quote is about a different candidate",
                )
                continue
            sources = classify_sources(self.tier_list, [Source(url=u) for u in urls])
            self._record_finding(candidate, raw, sources)

    def _extract_findings(self, criteria, candidate, text, visited):
        """No-fetch fallback: extract from search prose; ground via link-liveness."""
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
            live = self._live_sources(candidate, sources, raw.get("claim", ""))
            if live is None:
                continue
            self._record_finding(candidate, raw, live)

    def _live_sources(self, candidate, sources, claim):
        """Link-liveness filter (no-fetch path); returns None if nothing is live."""
        live = [s for s in sources if self._links.is_live(s.url)]
        for s in sources:
            if s not in live:
                self.log.log(
                    ev.EVENT_NOTE, stage="link-check", candidate=candidate.name,
                    dropped_url=s.url, reason="dead link (404/410/unreachable)",
                )
        if not live:
            self.log.log(
                ev.EVENT_NOTE, stage="link-check", candidate=candidate.name,
                dropped_claim=claim, reason="no live sources",
            )
            return None
        return live

    def _record_finding(self, candidate, raw, sources):
        """Build, classify-log, evaluate and record a finding from raw + live sources."""
        for s in sources:
            self.log.log(
                ev.EVENT_CLASSIFICATION, candidate=candidate.name,
                url=s.url, tier=s.tier, rule=s.tier_rule,
            )
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
        self.log.log(
            ev.EVENT_SOURCE_TIER_MIX, candidate=candidate.name, claim=finding.claim,
            **self._tier_mix(finding),
        )
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
        # Credible strength: distinct credible hosts OR best reviewer-corroboration,
        # so many user reviews on one marketplace satisfy the floor.
        return candidate_credible_strength(candidate.findings)

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

        self._ingest(criteria, candidate, merged_sources, "\n".join(text_parts))

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
            self._ingest(criteria, candidate, research.sources, research.text)
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
            self._candidate_brands = {self._brand_token(c.name) for c in candidates}
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
                            f"is too token-heavy for this ceiling. Raise --token-ceiling, "
                            f"reduce --max-subagents, or use a cheaper model."
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
        self._fetcher.close()
        return criteria, ranked, document
