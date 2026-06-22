# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/llm.py — Anthropic Messages-API client with web_search.
#
# Wraps the agentic tool-use loop: a research turn runs the server-side
# web_search tool (bounded by max_uses and iteration count), handles the
# `pause_turn` continuation, and accumulates token usage against a hard ceiling.
# A separate `extract` call returns validated JSON via output_config.format —
# the "boring" structured-output path, used to condense findings and criteria.
#
# Model and provider are configurable (sovereign/cloud split). The API key is
# passed straight to the SDK; it is never logged.
#
# Writes: read-only (network egress to the configured provider + open web)
# Idempotent: no (LLM calls)
# Requires: anthropic SDK; a valid API key in the environment

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic

from .config import Config
from .models import Source


class CostCeilingReached(RuntimeError):
    """Raised when cumulative token usage reaches the configured ceiling."""


@dataclass
class ResearchResult:
    text: str
    sources: list[Source]  # web_search results surfaced during the turn
    queries: list[str]  # search queries the model issued
    allowed_domains: list[str] | None = None  # steering applied this pass
    blocked_domains: list[str] | None = None
    degraded: bool = False  # provider rejected domain steering -> ran unsteered
    degraded_reason: str = ""  # the rejection message (diagnostics)


class LLMClient:
    """Thin, auditable wrapper over the Anthropic Messages API."""

    def __init__(self, config: Config) -> None:
        self.config = config
        kwargs: dict[str, Any] = {}
        if config.auth_mode == "subscription":
            # Let the SDK resolve the Claude OAuth credential (ant profile /
            # ANTHROPIC_AUTH_TOKEN). OAuth on /v1/messages needs this beta header.
            kwargs["default_headers"] = {"anthropic-beta": "oauth-2025-04-20"}
        else:
            kwargs["api_key"] = config.resolve_api_key()
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self.tokens_used = 0
        # Set False permanently if the provider rejects domain steering once.
        self._steering_supported = True

    # ---- token accounting -------------------------------------------------

    def _account(self, usage: Any) -> None:
        if usage is None:
            return
        for attr in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            self.tokens_used += getattr(usage, attr, 0) or 0

    def check_ceiling(self) -> None:
        if self.tokens_used >= self.config.token_ceiling:
            raise CostCeilingReached(
                f"token ceiling reached: {self.tokens_used} >= {self.config.token_ceiling}"
            )

    # ---- core calls -------------------------------------------------------

    def _create(self, **kwargs: Any) -> Any:
        self.check_ceiling()
        resp = self._client.messages.create(model=self.config.model, **kwargs)
        self._account(getattr(resp, "usage", None))
        return resp

    def _web_search_tool(
        self, allowed_domains: list[str] | None, blocked_domains: list[str] | None
    ) -> dict[str, Any]:
        tool: dict[str, Any] = {
            "type": self.config.web_search_tool_type(),
            "name": "web_search",
            "max_uses": self.config.max_search_uses_per_thread,
        }
        if self._steering_supported:
            # allowed_domains and blocked_domains are mutually exclusive on one tool.
            if allowed_domains:
                tool["allowed_domains"] = allowed_domains
            elif blocked_domains:
                tool["blocked_domains"] = blocked_domains
        return tool

    def research(
        self,
        system: str,
        prompt: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> ResearchResult:
        """Run one research turn with web_search; loop over pause_turn safely.

        Pass `allowed_domains` for a high-trust pass or `blocked_domains` for the
        open pass. If the provider rejects domain steering, retry once unsteered
        and mark the result degraded (the run continues — design D1 / OQ6).
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        sources: list[Source] = []
        queries: list[str] = []
        text_parts: list[str] = []
        degraded = False
        degraded_reason = ""

        for _ in range(self.config.max_iterations_per_thread):
            tool = self._web_search_tool(allowed_domains, blocked_domains)
            kwargs: dict[str, Any] = {
                "max_tokens": 8000,
                "system": system,
                "tools": [tool],
                "messages": messages,
            }
            if self.config.uses_advanced_reasoning():
                kwargs["thinking"] = {"type": "adaptive"}
                kwargs["output_config"] = {"effort": self.config.effort}
            try:
                resp = self._create(**kwargs)
            except anthropic.BadRequestError as exc:
                msg = str(exc).lower()
                if self._steering_supported and (
                    "allowed_domains" in msg or "blocked_domains" in msg or "domain" in msg
                ):
                    # Degrade gracefully: disable steering for the rest of the run.
                    self._steering_supported = False
                    degraded = True
                    degraded_reason = str(exc)[:300]
                    continue
                raise
            self._collect(resp, sources, queries, text_parts)

            if resp.stop_reason == "pause_turn":
                # Server-tool loop paused; re-send to resume (no extra message).
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": resp.content},
                ]
                continue
            break  # end_turn / max_tokens / refusal — stop the thread

        applied = self._steering_supported and not degraded
        return ResearchResult(
            text="\n".join(p for p in text_parts if p),
            sources=sources,
            queries=queries,
            allowed_domains=allowed_domains if applied else None,
            blocked_domains=blocked_domains if applied else None,
            degraded=degraded or not self._steering_supported,
            degraded_reason=degraded_reason,
        )

    def extract(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return JSON validated against `schema` (no tools, deterministic shape)."""
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
        kwargs: dict[str, Any] = {
            "max_tokens": 8000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.config.uses_advanced_reasoning():
            kwargs["thinking"] = {"type": "adaptive"}
            output_config["effort"] = self.config.effort
        kwargs["output_config"] = output_config
        resp = self._create(**kwargs)
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"structured extraction returned invalid JSON: {exc}") from exc

    # ---- response parsing -------------------------------------------------

    @staticmethod
    def _collect(
        resp: Any,
        sources: list[Source],
        queries: list[str],
        text_parts: list[str],
    ) -> None:
        """Pull text, search queries and web_search results out of a response."""
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "server_tool_use" and getattr(block, "name", "") == "web_search":
                q = (getattr(block, "input", {}) or {}).get("query")
                if q:
                    queries.append(q)
            elif btype == "web_search_tool_result":
                content = getattr(block, "content", None)
                # Success content is a list of web_search_result; error is an object.
                if isinstance(content, list):
                    for item in content:
                        url = getattr(item, "url", None)
                        if url:
                            sources.append(
                                Source(url=url, title=getattr(item, "title", "") or "")
                            )
