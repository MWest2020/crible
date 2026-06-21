# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# tests/test_core.py — unit tests for the deterministic (no-API) core.
#
# Covers source classification, within-source skepticism + corroboration,
# ranking neutrality + disqualification, audit-trail redaction, and config
# defaults. The live LLM path (orchestrator/llm) needs an API key and is
# exercised by the worked-example run, not here.
#
# Run: uv run pytest

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crible.audit import AuditLog, EVENT_NOTE
from crible.config import ConfigError, load_config
from crible.models import Candidate, Criteria, Finding, Source
from crible.ranking import rank
from crible.skepticism import classify_sources, count_independent, evaluate_finding
from crible.sources import TierList

TIERS = Path(__file__).resolve().parent.parent / "config" / "source_tiers.yaml"


@pytest.fixture
def tier_list() -> TierList:
    return TierList.load(TIERS)


# ---- source classification -----------------------------------------------

def test_affiliate_toplist_is_low(tier_list: TierList) -> None:
    s = tier_list.classify("https://example.com/best-10-thermos-review/")
    assert s.tier == "low"
    assert s.tier_rule  # an explicit rule produced it, not a black box


def test_marketplace_is_medium(tier_list: TierList) -> None:
    # Marketplaces host user reviews (lived experience, gameable) — ranked
    # above blogs, below specialist fora.
    assert tier_list.classify("https://www.amazon.com/dp/B000").tier == "medium"


def test_manufacturer_blog_is_low(tier_list: TierList) -> None:
    assert tier_list.classify("https://holohololife.com/blogs/news/sus316").tier == "low"


def test_known_affiliate_blog_is_low(tier_list: TierList) -> None:
    assert tier_list.classify("https://www.homegrounds.co/zojirushi-mug-review/").tier == "low"


def test_reddit_is_high(tier_list: TierList) -> None:
    s = tier_list.classify("https://www.reddit.com/r/coffee/comments/x")
    assert s.tier == "high"
    assert s.tier_rule == "forum-reddit"


def test_coffee_forum_is_high(tier_list: TierList) -> None:
    assert tier_list.classify("https://www.coffeeforums.com/threads/odd-taste.7883/").tier == "high"


def test_evidence_hierarchy_weights() -> None:
    from crible.ranking import _TIER_WEIGHT
    assert _TIER_WEIGHT["high"] > _TIER_WEIGHT["medium"] > _TIER_WEIGHT["low"]
    assert _TIER_WEIGHT["medium"] > _TIER_WEIGHT["unknown"] > _TIER_WEIGHT["low"]


def test_unknown_when_unmatched(tier_list: TierList) -> None:
    s = tier_list.classify("https://some-random-blog.example/post")
    assert s.tier == "unknown"
    assert s.tier_rule == "unmatched"


# ---- skepticism / corroboration ------------------------------------------

def test_single_source_is_not_evidence(tier_list: TierList) -> None:
    f = Finding(
        candidate="X", kind="failure", claim="metallic taste",
        sources=classify_sources(tier_list, [Source(url="https://reddit.com/r/coffee/1")]),
    )
    fired = evaluate_finding(f, threshold=2)
    assert "single-source-not-evidence" in fired
    assert f.corroboration_count == 1


def test_independent_corroboration_counts_distinct_credible_hosts(tier_list: TierList) -> None:
    srcs = classify_sources(tier_list, [
        Source(url="https://reddit.com/r/coffee/1"),
        Source(url="https://reddit.com/r/coffee/2"),  # same host -> not independent
        Source(url="https://community.example/threads/9"),
    ])
    assert count_independent(srcs) == 2


def test_blogs_are_echo_chamber_zero_corroboration(tier_list: TierList) -> None:
    # Ten affiliate blogs are not corroboration — credible count must be zero.
    blogs = classify_sources(tier_list, [
        Source(url=f"https://www.homegrounds.co/review-{i}/") for i in range(10)
    ])
    assert count_independent(blogs) == 0
    f = Finding(candidate="X", kind="support", claim="great", sources=blogs,
                corroboration_count=10)  # model claimed 10
    fired = evaluate_finding(f, threshold=2)
    assert "no-credible-source-echo-chamber" in fired
    assert f.corroboration_count == 0


def test_user_review_count_is_honoured(tier_list: TierList) -> None:
    # One marketplace reviews page the model says has 7 independent reviewers.
    srcs = classify_sources(tier_list, [
        Source(url="https://www.amazon.com/dp/B000/product-reviews"),
    ])
    f = Finding(candidate="X", kind="support", claim="no metallic taste",
                sources=srcs, corroboration_count=7)
    evaluate_finding(f, threshold=2)
    assert f.corroboration_count == 7  # honoured (credible host present)


# ---- ranking --------------------------------------------------------------

def test_corroborated_disqualifier_disqualifies(tier_list: TierList) -> None:
    srcs = classify_sources(tier_list, [
        Source(url="https://reddit.com/r/coffee/1"),
        Source(url="https://community.example/threads/9"),
    ])
    f = Finding(candidate="A", kind="failure", claim="metallic taste",
                severity="disqualifying", sources=srcs)
    evaluate_finding(f, threshold=2)
    cand = Candidate(name="A", findings=[f])
    ranked = rank([cand], corroboration_threshold=2)
    assert ranked[0].disqualified is True


def test_clean_candidate_outranks_disqualified(tier_list: TierList) -> None:
    bad_srcs = classify_sources(tier_list, [
        Source(url="https://reddit.com/r/coffee/1"),
        Source(url="https://community.example/threads/9"),
    ])
    bad = Candidate(name="Bad", findings=[
        Finding(candidate="Bad", kind="failure", claim="metallic taste",
                severity="disqualifying", sources=bad_srcs),
    ])
    good_srcs = classify_sources(tier_list, [Source(url="https://reddit.com/r/coffee/2")])
    good = Candidate(name="Good", findings=[
        Finding(candidate="Good", kind="support", claim="no metallic taste reported",
                sources=good_srcs),
    ])
    for c in (bad, good):
        for f in c.findings:
            evaluate_finding(f, threshold=2)
    ranked = rank([bad, good], corroboration_threshold=2)
    assert ranked[0].name == "Good"
    assert ranked[0].disqualified is False


# ---- audit redaction ------------------------------------------------------

def test_audit_redacts_secret(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "run", secrets=["sk-ant-SECRET"])
    log.log(EVENT_NOTE, note="contains sk-ant-SECRET inline")
    line = (tmp_path / "run" / "audit.jsonl").read_text().strip()
    record = json.loads(line)
    assert "sk-ant-SECRET" not in line
    assert "***REDACTED***" in record["note"]


def test_audit_line_is_standalone_json(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "run")
    log.log(EVENT_NOTE, a=1)
    log.log(EVENT_NOTE, b=2)
    lines = (tmp_path / "run" / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 2
    for ln in lines:
        rec = json.loads(ln)
        assert "ts" in rec and "type" in rec


# ---- config ---------------------------------------------------------------

def test_config_defaults_are_safe() -> None:
    cfg = load_config()
    assert cfg.parallelism_enabled is False  # default OFF
    assert cfg.token_ceiling > 0
    assert cfg.corroboration_threshold >= 2


def test_config_rejects_unknown_override() -> None:
    with pytest.raises(ConfigError):
        load_config(nonexistent_knob=1)


def test_web_search_tool_version_tracks_model() -> None:
    assert load_config(model="claude-opus-4-8").web_search_tool_type() == "web_search_20260209"
    assert load_config(model="claude-3-haiku-20240307").web_search_tool_type() == "web_search_20250305"


def test_render_advice_smoke() -> None:
    from crible.advice import render
    crit = Criteria(question="best thermos", disqualifiers=["metallic taste"])
    doc = render(crit, [])
    assert "# Crible advice" in doc
    assert "metallic taste" in doc


# ---- retrieval steering + evidence-mix -----------------------------------

def test_steering_domain_lists_from_seed(tier_list: TierList) -> None:
    allow = tier_list.allow_domains()
    block = tier_list.block_domains()
    assert "reddit.com" in allow and "home-barista.com" in allow
    assert "homegrounds.co" in block
    # Bare substrings like "amazon." are not valid domains -> skipped, not emitted.
    assert not any(d.endswith(".") for d in allow + block)
    assert "amazon" not in allow


def test_extra_passes_clamped_to_one() -> None:
    assert load_config(evidence_research_extra_passes=5).evidence_research_extra_passes == 1
    assert load_config(evidence_research_extra_passes=0).evidence_research_extra_passes == 0


class _FakeClient:
    """Stand-in for LLMClient: serves queued research/extract results, no network."""

    def __init__(self, research_results, extract_results):
        self._research = list(research_results)
        self._extract = list(extract_results)
        self.research_calls = 0
        self.extract_calls = 0
        self.tokens_used = 0

    def check_ceiling(self):
        pass

    def research(self, system, prompt, allowed_domains=None, blocked_domains=None):
        self.research_calls += 1
        from crible.llm import ResearchResult
        return self._research.pop(0) if self._research else ResearchResult("", [], [])

    def extract(self, system, prompt, schema):
        self.extract_calls += 1
        return self._extract.pop(0) if self._extract else {"findings": []}


def _rr(url: str):
    from crible.llm import ResearchResult
    return ResearchResult(text="notes", sources=[Source(url=url)], queries=[])


def _support(url: str):
    return {"findings": [{
        "kind": "support", "claim": "ok", "criterion": "taste", "severity": "unknown",
        "corroboration_count": 5, "source_urls": [url], "skepticism_flags": [],
    }]}


def _make_orchestrator(monkeypatch, fake, tmp_path):
    from crible.orchestrator import Orchestrator
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")
    cfg = load_config(evidence_mix_floor=2, evidence_research_extra_passes=1)
    cfg.source_tiers_path = TIERS
    orch = Orchestrator(cfg, AuditLog(tmp_path / "run"))
    orch.client = fake  # bypass the real network client
    return orch


def test_floor_breach_triggers_one_research(monkeypatch, tmp_path) -> None:
    # First pass finds 1 credible source (below floor 2); re-search adds a second.
    fake = _FakeClient(
        research_results=[
            _rr("https://www.reddit.com/r/coffee/1"),   # high-trust pass
            _rr(""),                                     # open pass (nothing useful)
            _rr("https://www.home-barista.com/t/9"),     # the ONE re-search
        ],
        extract_results=[
            _support("https://www.reddit.com/r/coffee/1"),
            _support("https://www.home-barista.com/t/9"),
        ],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    cand = Candidate(name="X")
    orch.investigate(Criteria(question="q", disqualifiers=["metallic taste"]), cand)
    assert fake.research_calls == 3  # 2 passes + exactly one bounded re-search
    assert cand.caveat == ""  # floor met after re-search (2 distinct credible hosts)


def test_floor_not_met_emits_caveat_and_advice_surfaces_it(monkeypatch, tmp_path) -> None:
    from crible.advice import render
    blog = "https://www.homegrounds.co/review"  # low-tier echo chamber
    fake = _FakeClient(
        research_results=[_rr(blog), _rr(blog), _rr(blog)],
        extract_results=[_support(blog), _support(blog)],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    cand = Candidate(name="X")
    crit = Criteria(question="q", disqualifiers=["metallic taste"])
    orch.investigate(crit, cand)
    assert fake.research_calls == 3  # bounded — no loop
    assert cand.caveat == "evidence-mix-floor-not-met"
    doc = render(crit, [cand], corroboration_threshold=2)
    assert "evidence-mix-floor-not-met" in doc
