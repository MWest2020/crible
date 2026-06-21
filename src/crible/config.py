# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/config.py — explicit, auditable run configuration.
#
# Every knob is here, with safe defaults: parallelisation OFF, a token ceiling
# always set, corroboration threshold >= 2. The API key is read from the
# environment (or a .env loaded by the caller) and is NEVER hardcoded or logged.
#
# Writes: read-only
# Idempotent: yes
# Requires: ANTHROPIC_API_KEY in the environment for a live run

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Map a model id to the web_search server-tool version it supports.
# Newer models get the dynamic-filtering variant; older models the basic one.
_WEB_SEARCH_NEW = "web_search_20260209"
_WEB_SEARCH_BASIC = "web_search_20250305"
_NEW_SEARCH_MODELS = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-fable-5",
)


class ConfigError(RuntimeError):
    """Raised when configuration is invalid or a required secret is missing."""


@dataclass
class Config:
    """Resolved configuration for one research run."""

    # Provider / model (sovereign/cloud split via provider + base_url).
    provider: str = "anthropic"
    model: str = "claude-opus-4-8"
    base_url: str | None = None  # override endpoint (sovereign deployments)
    api_key_env: str = "ANTHROPIC_API_KEY"
    # Effort multiplies thinking + tool tokens on EVERY call; this agent makes
    # ~12 calls per run, so "medium" is the safer default. Bump to high/xhigh
    # (e.g. on Opus) only when you want maximum quality and accept the cost.
    effort: str = "medium"  # low | medium | high | xhigh | max

    # Cost / safety ceilings.
    token_ceiling: int = 200_000  # cumulative tokens; halts the run when reached

    # Orchestration.
    parallelism_enabled: bool = False  # default OFF — explicit opt-in only
    max_subagents: int = 8
    max_iterations_per_thread: int = 3  # bounded tool-use loop per thread
    max_search_uses_per_thread: int = 2  # web_search max_uses cap PER PASS (token-heavy)

    # Retrieval steering + evidence-mix (change: steer-retrieval-toward-trusted-sources).
    domain_steering_enabled: bool = True  # dual-pass allow/block steering
    evidence_mix_floor: int = 2  # min distinct high+medium sources before a clean verdict
    evidence_research_extra_passes: int = 1  # bounded re-search on floor breach (hard cap 1)
    # Domains Anthropic's web_search user agent CANNOT crawl — listing any of
    # them in allowed_domains 400s the whole request, so they are kept out of the
    # high-trust allow-list. (They can still appear in open-pass results; we just
    # cannot allow-list or server-fetch them. The client-side/local path can.)
    noncrawlable_search_domains: list[str] = field(default_factory=lambda: ["reddit.com"])
    # Augmentation templates. {topic} steers toward the topic's OWN specialist
    # community (not a reddit-only default); {candidate}/{disqualifier} hunt the
    # specific failure mode in lived experience.
    query_templates: list[str] = field(
        default_factory=lambda: [
            "best {topic} forum OR community",
            "{topic} enthusiast forum recommendations",
            "{candidate} {disqualifier} forum",
            "{candidate} {disqualifier} reddit",
            "{candidate} {disqualifier} review",
            "{candidate} long-term review experience",
        ]
    )

    # Skepticism / ranking.
    corroboration_threshold: int = 2  # >= 2 independent corroborations

    # Link liveness — a cited source MUST resolve, or it is dropped (broken links
    # are a no-go for the advice). 403/429 (bot-blocked) count as live; only
    # 404/410/unreachable are treated as dead.
    verify_links: bool = True
    link_check_timeout: float = 6.0

    # Content grounding — fetch the cited page ourselves (our host can reach
    # sources Anthropic's crawler can't, e.g. reddit) and verify the quote is
    # actually on the page. Subsumes link-liveness when enabled.
    fetch_enabled: bool = True
    max_fetch_pages_per_finding: int = 6
    max_fetch_chars: int = 20_000
    quote_match_ratio: float = 0.8

    # Known blog / affiliate / SEO domains to keep out of search results at the
    # source (an echo chamber that does not count as evidence anyway).
    blocked_search_domains: list[str] = field(
        default_factory=lambda: [
            "homegrounds.co",
            "perfectdailygrind.com",
            "thespruceeats.com",
            "gearjunkie.com",
            "wirecutter.com",
            "thegadgeteer.com",
            "imprintnow.com",
        ]
    )

    # Paths.
    source_tiers_path: Path = field(
        default_factory=lambda: Path("config/source_tiers.yaml")
    )
    runs_dir: Path = field(default_factory=lambda: Path("runs"))

    def web_search_tool_type(self) -> str:
        """Pick the web_search tool version that matches the configured model."""
        return _WEB_SEARCH_NEW if self.model in _NEW_SEARCH_MODELS else _WEB_SEARCH_BASIC

    def uses_advanced_reasoning(self) -> bool:
        """Whether the model accepts adaptive thinking + the effort parameter.

        Both error on Haiku 4.5 and older models, so they are sent only for the
        modern Opus/Sonnet/Fable tier. Other models simply run without them.
        """
        return self.model in _NEW_SEARCH_MODELS

    def resolve_api_key(self) -> str:
        """Read the API key from the environment; fail fast if absent.

        Never returns the key into a log or the audit trail — callers pass it
        straight to the SDK client.
        """
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise ConfigError(
                f"missing API key: set the {self.api_key_env} environment variable "
                "(crible never reads or stores credentials in files)"
            )
        return key

    def redaction_values(self) -> list[str]:
        """Secret values that must be scrubbed from any audit output."""
        key = os.environ.get(self.api_key_env, "").strip()
        return [key] if key else []

    def effective_settings(self) -> dict[str, Any]:
        """Non-secret settings recorded in the audit trail for reproducibility."""
        d = asdict(self)
        d["source_tiers_path"] = str(self.source_tiers_path)
        d["runs_dir"] = str(self.runs_dir)
        d["web_search_tool_type"] = self.web_search_tool_type()
        # api_key_env is the *name* of the env var, not the secret — safe to log.
        return d


def load_config(**overrides: Any) -> Config:
    """Build a Config from defaults, environment overrides, then explicit kwargs.

    Environment overrides (all optional):
      CRIBLE_MODEL, CRIBLE_PROVIDER, CRIBLE_BASE_URL, CRIBLE_EFFORT,
      CRIBLE_TOKEN_CEILING, CRIBLE_PARALLEL (0/1), CRIBLE_MAX_SUBAGENTS,
      CRIBLE_CORROBORATION_THRESHOLD, CRIBLE_SOURCE_TIERS, CRIBLE_RUNS_DIR
    Explicit kwargs win over the environment.
    """
    cfg = Config()

    env = os.environ
    if v := env.get("CRIBLE_MODEL"):
        cfg.model = v
    if v := env.get("CRIBLE_PROVIDER"):
        cfg.provider = v
    if v := env.get("CRIBLE_BASE_URL"):
        cfg.base_url = v
    if v := env.get("CRIBLE_EFFORT"):
        cfg.effort = v
    if v := env.get("CRIBLE_TOKEN_CEILING"):
        cfg.token_ceiling = int(v)
    if v := env.get("CRIBLE_PARALLEL"):
        cfg.parallelism_enabled = v.strip() in ("1", "true", "yes", "on")
    if v := env.get("CRIBLE_MAX_SUBAGENTS"):
        cfg.max_subagents = int(v)
    if v := env.get("CRIBLE_CORROBORATION_THRESHOLD"):
        cfg.corroboration_threshold = int(v)
    if v := env.get("CRIBLE_SOURCE_TIERS"):
        cfg.source_tiers_path = Path(v)
    if v := env.get("CRIBLE_RUNS_DIR"):
        cfg.runs_dir = Path(v)
    if v := env.get("CRIBLE_DOMAIN_STEERING"):
        cfg.domain_steering_enabled = v.strip() in ("1", "true", "yes", "on")
    if v := env.get("CRIBLE_EVIDENCE_MIX_FLOOR"):
        cfg.evidence_mix_floor = int(v)
    if v := env.get("CRIBLE_EVIDENCE_EXTRA_PASSES"):
        cfg.evidence_research_extra_passes = int(v)
    if v := env.get("CRIBLE_VERIFY_LINKS"):
        cfg.verify_links = v.strip() in ("1", "true", "yes", "on")
    if v := env.get("CRIBLE_LINK_TIMEOUT"):
        cfg.link_check_timeout = float(v)
    if v := env.get("CRIBLE_FETCH"):
        cfg.fetch_enabled = v.strip() in ("1", "true", "yes", "on")
    if v := env.get("CRIBLE_QUOTE_MATCH_RATIO"):
        cfg.quote_match_ratio = float(v)

    for key, value in overrides.items():
        if not hasattr(cfg, key):
            raise ConfigError(f"unknown config override: {key}")
        setattr(cfg, key, value)

    if cfg.token_ceiling <= 0:
        raise ConfigError("token_ceiling must be positive")
    if cfg.corroboration_threshold < 1:
        raise ConfigError("corroboration_threshold must be >= 1")
    if cfg.evidence_mix_floor < 1:
        raise ConfigError("evidence_mix_floor must be >= 1")
    # Hard cap the re-search at one extra pass — bounded, never a loop.
    cfg.evidence_research_extra_passes = max(0, min(1, cfg.evidence_research_extra_passes))
    return cfg
