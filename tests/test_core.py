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
