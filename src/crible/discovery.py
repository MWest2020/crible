# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/discovery.py — client-side discovery of URLs the provider misses.
#
# Anthropic's web_search never returns reddit (its crawler is blocked there), yet
# reddit is the #1 lived-experience source. We discover those URLs ourselves and
# feed them into the existing client-fetch + quote-verify pipeline. Pluggable
# backend; reddit first. Bounded, cached, and degradable: a backend error (block
# / rate-limit / timeout) yields no results and is reported, never raised.
#
# Writes: read-only (HTTP GET to the discovery backend)
# Idempotent: yes (cached per run)
# Requires: httpx

from __future__ import annotations

import re
import urllib.parse

import httpx

from .models import Source

_UA = "Mozilla/5.0 (compatible; crible/0.1; +https://github.com/MWest2020/crible)"


class DuckDuckGoBackend:
    """Discover URLs (incl. reddit + fora) via DuckDuckGo's HTML endpoint — no key.

    Reddit's own search blocks unauthenticated requests, but a general search engine
    returns reddit thread URLs (which we CAN then fetch). We bias toward lived
    experience by also running a reddit/forum-targeted variant of the query.
    """

    name = "duckduckgo"
    _RESULT = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', re.IGNORECASE)
    _REDDIT = re.compile(r'https?://[^"\s]*reddit\.com/r/[^"\s]+/comments/[^"\s]+')

    def __init__(self, timeout: float = 8.0, client: httpx.Client | None = None) -> None:
        self.timeout = timeout
        self._client = client

    def _ensure(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True, timeout=self.timeout, headers={"User-Agent": _UA}
            )
        return self._client

    @staticmethod
    def _unwrap(href: str) -> str | None:
        if "uddg=" in href:  # DDG redirect wrapper
            m = re.search(r"uddg=([^&]+)", href)
            return urllib.parse.unquote(m.group(1)) if m else None
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        return None

    def _query(self, q: str) -> list[str]:
        resp = self._ensure().get("https://html.duckduckgo.com/html/", params={"q": q})
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError("ddg blocked", request=resp.request, response=resp)
        urls = [u for h in self._RESULT.findall(resp.text) if (u := self._unwrap(h))]
        urls += self._REDDIT.findall(resp.text)  # fallback: any reddit thread links present
        return urls

    def search(self, query: str, limit: int) -> list[Source]:
        seen: set[str] = set()
        out: list[Source] = []
        # reddit/forum-biased variant first, then the plain query
        for q in (f"{query} reddit forum review", query):
            for url in self._query(q):
                if url not in seen:
                    seen.add(url)
                    out.append(Source(url=url))
                if len(out) >= limit:
                    return out
        return out

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


class RedditBackend:
    """Discover reddit thread URLs for a query via reddit's public search JSON."""

    name = "reddit"

    def __init__(self, timeout: float = 8.0, client: httpx.Client | None = None) -> None:
        self.timeout = timeout
        self._client = client

    def _ensure(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True, timeout=self.timeout, headers={"User-Agent": _UA}
            )
        return self._client

    def search(self, query: str, limit: int) -> list[Source]:
        """Return reddit thread URLs (raises on transport/HTTP error — caller degrades)."""
        resp = self._ensure().get(
            "https://www.reddit.com/search.json",
            params={"q": query, "limit": limit, "sort": "relevance", "type": "link"},
        )
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError("reddit search blocked", request=resp.request, response=resp)
        out: list[Source] = []
        for child in resp.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            permalink = d.get("permalink")
            if permalink:
                out.append(Source(url=f"https://www.reddit.com{permalink}", title=d.get("title", "")))
        return out[:limit]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


_BACKENDS = {"duckduckgo": DuckDuckGoBackend, "reddit": RedditBackend}


class Discovery:
    """Bounded, cached, degradable client-side discovery."""

    def __init__(
        self,
        backend_name: str = "duckduckgo",
        enabled: bool = True,
        max_results: int = 5,
        backend=None,
    ) -> None:
        self.enabled = enabled
        self.max_results = max_results
        self.backend_name = backend_name
        self._backend = backend or (
            _BACKENDS.get(backend_name, DuckDuckGoBackend)() if enabled else None
        )
        self._cache: dict[str, list[Source]] = {}
        self.last_error: str = ""

    def discover(self, query: str) -> list[Source]:
        """Return discovered sources for the query, or [] (and set last_error) on failure."""
        self.last_error = ""
        if not self.enabled or self._backend is None:
            return []
        if query in self._cache:
            return self._cache[query]
        try:
            results = self._backend.search(query, self.max_results)
        except Exception as exc:  # block / rate-limit / timeout -> degrade
            self.last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            results = []
        self._cache[query] = results
        return results

    def close(self) -> None:
        if self._backend is not None and hasattr(self._backend, "close"):
            self._backend.close()
