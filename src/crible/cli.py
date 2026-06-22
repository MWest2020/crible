# SPDX-License-Identifier: EUPL-1.2
# role: entrypoint
#
# src/crible/cli.py — command-line entry point.
#
# Usage:
#   crible "the best travel thermos for quality coffee, no metallic taste"
#   crible "..." --model claude-opus-4-8 --token-ceiling 150000 --effort medium
#   CRIBLE_PARALLEL=1 crible "..."        # opt in to parallel subagents (default OFF)
#
# Reads the API key from the environment (ANTHROPIC_API_KEY). A local .env is
# loaded if python-dotenv is installed, but its contents are never printed.
# Writes the advice to a per-run directory and prints it to stdout (OQ5).
#
# Writes: runs/<timestamp>/ (audit.jsonl, plan.json, advice.md)
# Idempotent: no (each run is a new directory; makes live API calls)
# Requires: ANTHROPIC_API_KEY in the environment for a live run

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .audit import AuditLog
from .config import ConfigError, load_config
from .orchestrator import Orchestrator


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > 45:
        s = s[:45].rsplit("-", 1)[0]  # trim to a whole word, not mid-word
    return s or "run"


def _run_dir(runs_dir, slug: str, stamp: str):
    """Readable, slug-forward run directory: <slug>_<YYYY-MM-DD>, with -2/-3 on clash."""
    base = f"{slug}_{stamp}"
    candidate = runs_dir / base
    n = 2
    while candidate.exists():
        candidate = runs_dir / f"{base}-{n}"
        n += 1
    return candidate


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="crible",
        description="Bias-correcting product-research agent (single-user, on-demand).",
    )
    p.add_argument("question", help="what you want the best product for")
    p.add_argument("--model", help="model id (default: claude-opus-4-8)")
    p.add_argument("--effort", help="low | medium | high | xhigh | max")
    p.add_argument("--token-ceiling", type=int, help="cumulative token cap for the run")
    p.add_argument("--max-subagents", type=int, help="cap on candidate threads")
    p.add_argument(
        "--corroboration-threshold",
        type=int,
        help="min independent corroborations before a claim affects ranking",
    )
    p.add_argument(
        "--evidence-mix-floor",
        type=int,
        help="min distinct high+medium sources before a clean verdict (default 2)",
    )
    p.add_argument(
        "--evidence-extra-passes",
        type=int,
        help="bounded high-trust re-searches on floor breach (0 or 1; default 1)",
    )
    p.add_argument(
        "--no-domain-steering",
        action="store_true",
        help="disable allow/block domain steering of web search",
    )
    p.add_argument(
        "--no-fetch",
        action="store_true",
        help="disable client-side page fetch + quote verification (fall back to link-liveness)",
    )
    p.add_argument(
        "--quote-match-ratio",
        type=float,
        help="token-overlap ratio to accept a quote as grounded (default 0.8)",
    )
    p.add_argument(
        "--subscription",
        action="store_true",
        help="auth via a Claude OAuth credential (ant profile) instead of an API key",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="run even if the question is too vague (skip the specificity gate)",
    )
    p.add_argument("--runs-dir", help="directory for run outputs (default: runs/)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    subscription = args.subscription or os.environ.get("CRIBLE_AUTH_MODE") == "subscription"
    # Load .env (for the API key) ONLY in api-key mode; in subscription mode a
    # stray ANTHROPIC_API_KEY would shadow the OAuth credential, so don't load it.
    if not subscription:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # pragma: no cover - optional dependency
            pass

    overrides: dict = {}
    if subscription:
        overrides["auth_mode"] = "subscription"
    if args.model:
        overrides["model"] = args.model
    if args.effort:
        overrides["effort"] = args.effort
    if args.token_ceiling:
        overrides["token_ceiling"] = args.token_ceiling
    if args.max_subagents:
        overrides["max_subagents"] = args.max_subagents
    if args.corroboration_threshold:
        overrides["corroboration_threshold"] = args.corroboration_threshold
    if args.evidence_mix_floor:
        overrides["evidence_mix_floor"] = args.evidence_mix_floor
    if args.evidence_extra_passes is not None:
        overrides["evidence_research_extra_passes"] = args.evidence_extra_passes
    if args.force:
        overrides["require_specific"] = False
    if args.no_domain_steering:
        overrides["domain_steering_enabled"] = False
    if args.no_fetch:
        overrides["fetch_enabled"] = False
    if args.quote_match_ratio is not None:
        overrides["quote_match_ratio"] = args.quote_match_ratio
    if args.runs_dir:
        overrides["runs_dir"] = Path(args.runs_dir)

    try:
        config = load_config(**overrides)
        config.resolve_api_key()  # fail fast before any work / network call
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = _run_dir(config.runs_dir, _slug(args.question), stamp)
    log = AuditLog(run_dir, secrets=config.redaction_values())

    orchestrator = Orchestrator(config, log)
    _criteria, _ranked, document = orchestrator.run(args.question)

    print(document)
    print(f"\n[run written to {run_dir}]", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
