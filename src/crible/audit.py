# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/audit.py — append-only JSONL audit trail, the system of record.
#
# One JSON object per line, each with a type and timestamp. A credential
# redaction guard ensures no API key value can ever be written to the trail.
# The verification pass and every other stage write through this logger so the
# record cannot drift from the decisions it documents.
#
# Writes: <run_dir>/audit.jsonl (append-only), plus the run directory itself
# Idempotent: no (appends a line per event)
# Requires: stdlib only

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Event types (kept explicit so the trail is greppable and auditable).
EVENT_RUN_SETTINGS = "run_settings"
EVENT_CRITERIA = "criteria"
EVENT_PLAN = "plan"
EVENT_QUERY = "query"
EVENT_SOURCE_VISITED = "source_visited"
EVENT_CLASSIFICATION = "classification"
EVENT_SKEPTICISM_RULE = "skepticism_rule"
EVENT_CORROBORATION = "corroboration"
EVENT_FINDING = "finding"
EVENT_SCORE = "score"
EVENT_DECISION = "decision"
EVENT_COST = "cost"
EVENT_DEDUP = "dedup"
EVENT_STOP = "stop"
EVENT_NOTE = "note"
# Retrieval-steering + evidence-mix events (change: steer-retrieval-toward-trusted-sources)
EVENT_SEARCH_DOMAINS = "search_domains"  # allowed/blocked domains per search pass
EVENT_QUERY_TEMPLATES = "query_templates"  # augmentation templates applied per search
EVENT_SOURCE_TIER_MIX = "source_tier_mix"  # per-finding / per-candidate tier counts
EVENT_FLOOR_CHECK = "floor_check"  # evidence-mix floor evaluation (before/after re-search)
EVENT_FLOOR_NOT_MET = "evidence_mix_floor_not_met"  # loud caveat: too few trusted sources
# Content grounding (change: ground-evidence-in-fetched-content)
EVENT_FETCH = "fetch"  # a cited page was fetched (url, ok, chars)
EVENT_QUOTE_CHECK = "quote_check"  # quote verified against fetched text (matched, score)


def _redact(value: Any, secrets: list[str]) -> Any:
    """Recursively replace any secret substring with a redaction marker."""
    if not secrets:
        return value
    if isinstance(value, str):
        out = value
        for secret in secrets:
            if secret and secret in out:
                out = out.replace(secret, "***REDACTED***")
        return out
    if isinstance(value, dict):
        return {k: _redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, secrets) for v in value]
    return value


class AuditLog:
    """Append-only JSONL writer for one run."""

    def __init__(self, run_dir: Path, secrets: list[str] | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "audit.jsonl"
        self._secrets = secrets or []
        # Touch the file so an empty run still leaves a trail.
        self.path.touch(exist_ok=True)

    def log(self, event_type: str, **fields: Any) -> None:
        """Append one event as a JSON line, redacting any secret values."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **fields,
        }
        safe = _redact(record, self._secrets)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(safe, ensure_ascii=False) + "\n")

    def write_json(self, name: str, data: Any) -> Path:
        """Write a side artefact (e.g. plan.json, advice.md) into the run dir."""
        out = self.run_dir / name
        safe = _redact(data, self._secrets)
        if name.endswith(".json"):
            out.write_text(json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            out.write_text(str(safe), encoding="utf-8")
        return out
