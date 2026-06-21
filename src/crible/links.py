# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/links.py — cited-link liveness checker.
#
# Broken links are a no-go for the advice, so every cited source URL is probed
# before it is allowed into a finding. Policy (deliberately conservative about
# NOT dropping real-but-bot-blocked sources):
#   - dead (drop):   404 / 410, or unreachable (DNS/connect/timeout/protocol)
#   - live (keep):   2xx / 3xx, and access-restricted 401 / 403 / 429 (the page
#                    exists; a human clicking the link will reach it)
# Results are cached per run so each distinct URL is probed at most once.
#
# Writes: read-only (HTTP HEAD/GET probes only)
# Idempotent: yes (cached)
# Requires: httpx

from __future__ import annotations

import httpx

_DEAD_STATUS = {404, 410}
_HEAD_UNSUPPORTED = {405, 501}
# Browser-like UA so bot-averse sites don't 403 us (and even if they do, we keep it).
_UA = "Mozilla/5.0 (compatible; crible/0.1; +https://github.com/MWest2020/crible)"


class LinkChecker:
    """Probes whether cited URLs resolve; caches results for the run."""

    def __init__(
        self,
        timeout: float = 6.0,
        enabled: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout = timeout
        self._cache: dict[str, bool] = {}
        self._client = client  # injectable for tests

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=self.timeout,
                headers={"User-Agent": _UA},
            )
        return self._client

    def is_live(self, url: str) -> bool:
        """True if the URL resolves (or is merely access-restricted)."""
        if not self.enabled:
            return True
        if url in self._cache:
            return self._cache[url]
        ok = self._probe(url)
        self._cache[url] = ok
        return ok

    def _probe(self, url: str) -> bool:
        client = self._ensure_client()
        try:
            resp = client.head(url)
            if resp.status_code in _HEAD_UNSUPPORTED:
                resp = client.get(url)
            return resp.status_code not in _DEAD_STATUS
        except Exception:
            # DNS failure, connection refused, timeout, protocol error -> dead.
            return False

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
