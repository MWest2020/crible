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

def test_subscription_mode_needs_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = load_config(auth_mode="subscription")
    assert cfg.resolve_api_key() == ""  # no key required in subscription mode


def test_api_key_mode_still_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        load_config().resolve_api_key()


def test_invalid_auth_mode_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config(auth_mode="bogus")


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
        "corroboration_count": 1, "source_urls": [url], "skepticism_flags": [],
    }]}


def _make_orchestrator(monkeypatch, fake, tmp_path):
    from crible.orchestrator import Orchestrator
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")
    # Disable link probing by default so floor tests don't hit the network;
    # tests that exercise link-dropping set orch._links explicitly.
    cfg = load_config(
        evidence_mix_floor=2, evidence_research_extra_passes=1,
        verify_links=False, fetch_enabled=False,
    )
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


# ---- link liveness + quotes ----------------------------------------------

class _FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code


class _FakeHTTP:
    """Minimal httpx.Client stand-in: status by URL substring."""

    def __init__(self, status_by_substr):
        self._map = status_by_substr

    def _status(self, url):
        for sub, code in self._map.items():
            if sub in url:
                return code
        return 200

    def head(self, url):
        return _FakeResp(self._status(url))

    def get(self, url):
        return _FakeResp(self._status(url))

    def close(self):
        pass


def test_link_checker_drops_dead_keeps_blocked() -> None:
    from crible.links import LinkChecker
    http = _FakeHTTP({"dead": 404, "gone": 410, "blocked": 403})
    lc = LinkChecker(client=http)
    assert lc.is_live("https://x.com/dead") is False
    assert lc.is_live("https://x.com/gone") is False
    assert lc.is_live("https://x.com/blocked") is True   # 403 = exists, bot-blocked
    assert lc.is_live("https://x.com/ok") is True


def test_link_checker_unreachable_is_dead() -> None:
    from crible.links import LinkChecker

    class _Boom:
        def head(self, url):
            raise RuntimeError("connect error")
        def get(self, url):
            raise RuntimeError("connect error")
        def close(self):
            pass

    lc = LinkChecker(client=_Boom())
    assert lc.is_live("https://nope.invalid/x") is False


def test_dead_link_finding_is_dropped(monkeypatch, tmp_path) -> None:
    # A finding whose only source is a dead link must not survive.
    dead = "https://www.reddit.com/r/coffee/DEAD"
    fake = _FakeClient(
        research_results=[_rr(dead), _rr("")],
        extract_results=[{"findings": [{
            "kind": "support", "claim": "ok", "quote": "tastes fine", "criterion": "taste",
            "severity": "unknown", "corroboration_count": 3, "source_urls": [dead],
            "skepticism_flags": [],
        }]}],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch._links = _DeadAllLinks()  # every link is dead
    cand = Candidate(name="X")
    orch.investigate(Criteria(question="q", disqualifiers=["metallic taste"]), cand)
    assert cand.findings == []  # dropped: no live grounding


class _DeadAllLinks:
    def is_live(self, url):
        return False
    def close(self):
        pass


def test_allow_list_excludes_noncrawlable(monkeypatch, tmp_path) -> None:
    # reddit.com is blocked from Anthropic's crawler -> must not be allow-listed
    # (listing it 400s the whole request), but crawlable fora stay.
    orch = _make_orchestrator(monkeypatch, _FakeClient([], []), tmp_path)
    assert "reddit.com" not in orch._allow_domains
    assert "home-barista.com" in orch._allow_domains


def test_quote_matches_substring_and_overlap() -> None:
    from crible.fetch import quote_matches
    page = "Lots of text. I couldn't detect any metallic taste after a year of use. More."
    # exact (normalised) substring
    ok, score = quote_matches("I couldn't detect any metallic taste", page, 0.8)
    assert ok and score == 1.0
    # token-overlap above ratio (reordered/extra words)
    ok, score = quote_matches("metallic taste detect couldn't any after", page, 0.8)
    assert ok and score >= 0.8
    # fabricated quote -> no match
    ok, score = quote_matches("this thermos exploded and caught fire instantly", page, 0.8)
    assert not ok
    # very short quote requires substring
    assert quote_matches("metallic zzz", page, 0.8) == (False, 0.0)


def test_content_fetcher_dead_and_extract() -> None:
    from crible.fetch import ContentFetcher

    class _Resp:
        def __init__(self, code, text=""):
            self.status_code = code
            self.text = text

    class _HTTP:
        def __init__(self):
            self.calls = 0
        def get(self, url):
            self.calls += 1
            if "dead" in url:
                return _Resp(404)
            return _Resp(200, "<html><script>x=1</script><p>hello world</p></html>")
        def close(self):
            pass

    http = _HTTP()
    f = ContentFetcher(client=http)
    assert f.fetch("https://x.com/dead") is None
    text = f.fetch("https://x.com/ok")
    assert "hello world" in text and "x=1" not in text  # script stripped
    f.fetch("https://x.com/ok")
    assert http.calls == 2  # cached: 2 distinct URLs, second fetch not re-requested


class _FakeFetcher:
    def __init__(self, text):
        self._text = text
    def fetch(self, url):
        return self._text
    def close(self):
        pass


def test_unverifiable_quote_is_dropped(monkeypatch, tmp_path) -> None:
    # Fetch on, but the fetched page does NOT contain the model's quote -> drop.
    url = "https://www.home-barista.com/t/9"
    fake = _FakeClient(
        research_results=[_rr(url), _rr("")],
        extract_results=[{"findings": [{
            "kind": "support", "claim": "great", "quote": "this quote is not on the page at all",
            "criterion": "taste", "severity": "unknown", "corroboration_count": 3,
            "source_urls": [url], "skepticism_flags": [],
        }]}],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch.config.fetch_enabled = True
    orch._fetcher = _FakeFetcher("totally unrelated page content about something else")
    cand = Candidate(name="X")
    orch.investigate(Criteria(question="q", topic="t", disqualifiers=["metallic taste"]), cand)
    assert cand.findings == []  # quote not grounded -> dropped


def test_grounded_quote_is_kept(monkeypatch, tmp_path) -> None:
    url = "https://www.home-barista.com/t/9"
    quote = "no metallic taste even after months"
    fake = _FakeClient(
        research_results=[_rr(url), _rr("")],
        extract_results=[{"findings": [{
            "kind": "support", "claim": "great", "quote": quote,
            "criterion": "taste", "severity": "unknown", "corroboration_count": 3,
            "source_urls": [url], "skepticism_flags": [],
        }]}],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch.config.fetch_enabled = True
    orch._fetcher = _FakeFetcher(f"long forum thread ... {quote} ... more discussion")
    cand = Candidate(name="X")
    orch.investigate(Criteria(question="q", topic="t", disqualifiers=["metallic taste"]), cand)
    assert len(cand.findings) == 1 and cand.findings[0].quote == quote


def test_disqualifier_must_be_proven_for_recommendation() -> None:
    from crible.advice import _disqualifier_proven, render
    crit = Criteria(question="best thermos", disqualifiers=["metallic taste"])
    src = [Source(url="https://reddit.com/r/coffee/1", tier="high"),
           Source(url="https://www.home-barista.com/t/9", tier="high")]
    heat = Finding(candidate="A", kind="support", claim="keeps hot",
                   criterion="keeps coffee hot", sources=src, corroboration_count=2)
    cand = Candidate(name="A", findings=[heat])
    # credible support exists, but NOT about the disqualifier -> not proven
    assert _disqualifier_proven(cand, crit.disqualifiers) is False
    doc = render(crit, [cand], corroboration_threshold=2)
    assert "NOT proven by lived experience" in doc
    # add a disqualifier-addressing credible finding -> proven
    taste = Finding(candidate="A", kind="support", claim="no metal taste",
                    criterion="metallic taste", sources=src, corroboration_count=2)
    cand2 = Candidate(name="A", findings=[heat, taste])
    assert _disqualifier_proven(cand2, crit.disqualifiers) is True


def test_no_disqualifier_means_vacuously_proven() -> None:
    from crible.advice import _disqualifier_proven
    cand = Candidate(name="A")
    assert _disqualifier_proven(cand, []) is True


def test_themed_match_general_safety_counts_for_safety_disqualifier() -> None:
    from crible.advice import _addresses_disqualifier
    safe = Finding(candidate="A", kind="support", claim="safest trampolines",
                   criterion="safe design")
    # general safety praise addresses a pinch-point/safety disqualifier (loosened)
    assert _addresses_disqualifier(safe, ["known pinch-point injury hazards"]) is True
    # but a heat finding does NOT count toward a taste disqualifier
    hot = Finding(candidate="A", kind="support", claim="keeps coffee hot 6h",
                  criterion="keeps coffee hot")
    assert _addresses_disqualifier(hot, ["metallic taste"]) is False


def test_quote_attribution_guard_drops_offtopic(monkeypatch, tmp_path) -> None:
    # A quote about a DIFFERENT product (Stanley) must not attach to Zojirushi.
    url = "https://www.home-barista.com/t/9"
    fake = _FakeClient(
        research_results=[_rr(url), _rr("")],
        extract_results=[{"findings": [{
            "kind": "support", "claim": "hot", "quote": "my Stanley keeps coffee hot all day",
            "criterion": "keeps coffee hot", "severity": "unknown", "corroboration_count": 2,
            "source_urls": [url], "skepticism_flags": [],
        }]}],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch.config.fetch_enabled = True
    orch._fetcher = _FakeFetcher("forum: my Stanley keeps coffee hot all day, love it")
    orch._candidate_brands = {"zojirushi", "stanley"}  # Stanley is another candidate
    cand = Candidate(name="Zojirushi SM-SF48")
    orch.investigate(Criteria(question="q", topic="t", disqualifiers=["metallic taste"]), cand)
    # quote names 'stanley' (another candidate), not 'zojirushi' -> dropped as misattributed
    assert cand.findings == []


def test_attribution_keeps_generic_review(monkeypatch, tmp_path) -> None:
    # A real review that names no brand must be KEPT (most reviews don't repeat the brand).
    url = "https://www.amazon.com/dp/B000/product-reviews"
    fake = _FakeClient(
        research_results=[_rr(url), _rr("")],
        extract_results=[{"findings": [{
            "kind": "support", "claim": "hot", "quote": "keeps my coffee hot for 8 hours, love it",
            "criterion": "keeps coffee hot", "severity": "unknown", "corroboration_count": 2,
            "source_urls": [url], "skepticism_flags": [],
        }]}],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch.config.fetch_enabled = True
    orch._fetcher = _FakeFetcher("Amazon review: keeps my coffee hot for 8 hours, love it")
    orch._candidate_brands = {"zojirushi", "stanley"}
    cand = Candidate(name="Zojirushi SM-SF48")
    orch.investigate(Criteria(question="q", topic="t", disqualifiers=["metallic taste"]), cand)
    assert len(cand.findings) == 1  # no other brand named -> kept


def test_run_dir_is_slug_forward(tmp_path) -> None:
    from crible.cli import _run_dir, _slug
    d = _run_dir(tmp_path, _slug("the best travel thermos, no metallic taste"), "2026-06-21")
    assert d.name.startswith("the-best-travel-thermos")
    assert d.name.endswith("2026-06-21")
    assert "T" not in d.name and "Z" not in d.name  # no ugly ISO stamp


def test_vague_question_is_gated_before_spending(monkeypatch, tmp_path) -> None:
    # An over-vague question is stopped before any search (saves quota).
    fake = _FakeClient(
        research_results=[],
        extract_results=[{
            "topic": "trampoline", "positive": [], "disqualifiers": [],
            "budget": None, "context": None, "specific_enough": False,
            "clarifying_questions": ["What's your budget?", "What size/space?"],
        }],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    _crit, ranked, doc = orch.run("a safe trampoline")
    assert ranked == []
    assert fake.research_calls == 0  # gated before any landscape/subagent search
    assert "more specific" in doc and "What's your budget?" in doc


def test_build_landscape_derives_from_community(monkeypatch, tmp_path) -> None:
    # Candidates are extracted from fetched community text, not invented.
    url = "https://www.reddit.com/r/coffee/best-thermos"
    fake = _FakeClient(
        research_results=[_rr(url), _rr("")],  # two landscape search passes
        extract_results=[{
            "candidates": [{"name": "Zojirushi SM-SF48", "provenance": url}],
            "plan": ["hunt metallic taste reports"],
        }],
    )
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch.config.fetch_enabled = True
    orch._fetcher = _FakeFetcher("reddit: people love the Zojirushi SM-SF48, no metal taste at all")
    cands = orch.build_landscape(Criteria(question="best thermos", topic="travel thermos"))
    assert [c.name for c in cands] == ["Zojirushi SM-SF48"]
    assert cands[0].provenance == url
    assert fake.research_calls == 2  # community search (two passes)


def test_reddit_backend_parses_threads() -> None:
    from crible.discovery import RedditBackend

    class _Resp:
        status_code = 200
        request = None
        def json(self):
            return {"data": {"children": [
                {"data": {"permalink": "/r/Coffee/comments/lfcpyk/thermos/", "title": "metallic taste"}},
                {"data": {"permalink": "/r/Coffee/comments/abc/x/", "title": "x"}},
                {"data": {"title": "no permalink"}},
            ]}}

    class _HTTP:
        def get(self, url, params=None):
            assert "search.json" in url
            return _Resp()

    b = RedditBackend(client=_HTTP())
    out = b.search("thermos metallic taste", 5)
    assert [s.url for s in out] == [
        "https://www.reddit.com/r/Coffee/comments/lfcpyk/thermos/",
        "https://www.reddit.com/r/Coffee/comments/abc/x/",
    ]


def test_ddg_backend_parses_and_unwraps() -> None:
    from crible.discovery import DuckDuckGoBackend

    html = (
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reddit.com'
        '%2Fr%2FCoffee%2Fcomments%2Flfcpyk%2Fx%2F&rut=z">thread</a>'
        '<a class="result__a" href="https://home-barista.com/t/9">forum</a>'
    )

    class _Resp:
        status_code = 200
        request = None
        text = html

    class _HTTP:
        def get(self, url, params=None):
            return _Resp()

    b = DuckDuckGoBackend(client=_HTTP())
    urls = [s.url for s in b.search("thermos metallic taste", 6)]
    assert "https://www.reddit.com/r/Coffee/comments/lfcpyk/x/" in urls  # uddg unwrapped
    assert "https://home-barista.com/t/9" in urls


def test_discovery_degrades_on_error() -> None:
    from crible.discovery import Discovery

    class _Boom:
        name = "reddit"
        def search(self, q, n):
            raise RuntimeError("429 blocked")

    d = Discovery(backend=_Boom(), enabled=True, max_results=5)
    assert d.discover("anything") == []   # degrades, no raise
    assert "429" in d.last_error


def test_discovery_disabled_returns_empty() -> None:
    from crible.discovery import Discovery
    d = Discovery(enabled=False)
    assert d.discover("x") == []


def test_discovered_urls_are_merged_into_retrieved_sources(monkeypatch, tmp_path) -> None:
    # The provider's web_search returns nothing; client-side discovery surfaces the
    # reddit thread, and it must reach _ingest (the retrieved source set).
    from crible.discovery import Discovery

    thread = "https://www.reddit.com/r/Coffee/comments/lfcpyk/thermos_metallic_taste/"

    class _Found:
        name = "duckduckgo"
        def search(self, q, n):
            return [Source(url=thread, title="metallic taste thread")]

    fake = _FakeClient(research_results=[_rr(""), _rr("")], extract_results=[])
    orch = _make_orchestrator(monkeypatch, fake, tmp_path)
    orch._discovery = Discovery(backend=_Found(), enabled=True, max_results=5)

    seen: list[str] = []
    real_ingest = orch._ingest
    def _spy(criteria, candidate, sources, search_text):
        seen.extend(s.url for s in sources)
        return real_ingest(criteria, candidate, sources, search_text)
    orch._ingest = _spy

    orch.investigate(Criteria(question="q", disqualifiers=["metallic taste"]),
                     Candidate(name="X"))
    assert thread in seen  # discovered reddit URL merged into the retrieved set


def test_quote_is_rendered_in_advice() -> None:
    from crible.advice import render
    src = [Source(url="https://www.reddit.com/r/coffee/1", tier="high")]
    f = Finding(candidate="A", kind="support", claim="no metallic taste",
                quote="still no metal taste after a year", criterion="taste",
                sources=src, corroboration_count=2)
    cand = Candidate(name="A", findings=[f])
    doc = render(Criteria(question="q"), [cand], corroboration_threshold=2)
    assert "still no metal taste after a year" in doc
