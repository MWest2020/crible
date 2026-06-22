# SPDX-License-Identifier: EUPL-1.2
# role: library
#
# src/crible/fetch.py — client-side page fetch + quote verification.
#
# The trust spine of the advice: we fetch the cited page ourselves (our host can
# reach sources Anthropic's crawler cannot, e.g. reddit), and verify that a
# finding's quote actually appears on that page. A quote that cannot be grounded
# in fetched text is dropped — verified grounding, or no claim. Fetching also
# subsumes link-liveness: a page that won't fetch is dead.
#
# Quote matching is explicit and auditable (no learned model): normalise, then
# exact-substring OR token-overlap >= a configurable ratio.
#
# Writes: read-only (HTTP GET probes only)
# Idempotent: yes (cached per run)
# Requires: httpx

from __future__ import annotations

import html
import re

import httpx

_UA = "Mozilla/5.0 (compatible; crible/0.1; +https://github.com/MWest2020/crible)"
_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_NORM_STRIP = re.compile(r"[^\w\s]")  # drop punctuation for matching


def html_to_text(raw: str) -> str:
    """Minimal HTML -> text: drop script/style, strip tags, unescape, collapse ws."""
    no_blocks = _SCRIPT_STYLE.sub(" ", raw)
    stripped = _TAG.sub(" ", no_blocks)
    return _WS.sub(" ", html.unescape(stripped)).strip()


def normalise(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for robust matching."""
    return _WS.sub(" ", _NORM_STRIP.sub(" ", text.lower())).strip()


def quote_matches(quote: str, page_text: str, ratio: float) -> tuple[bool, float]:
    """Is `quote` grounded in `page_text`? Returns (matched, score).

    Exact normalised substring -> score 1.0. Otherwise token-overlap =
    (quote tokens present in page) / (quote tokens); matched if >= ratio. Very
    short quotes (<4 tokens) require the substring match (overlap is unreliable).
    """
    nq, npage = normalise(quote), normalise(page_text)
    if not nq:
        return False, 0.0
    if nq in npage:
        return True, 1.0
    q_tokens = nq.split()
    if len(q_tokens) < 4:
        return False, 0.0
    page_tokens = set(npage.split())
    present = sum(1 for t in q_tokens if t in page_tokens)
    score = present / len(q_tokens)
    return score >= ratio, score


class ContentFetcher:
    """Fetches and caches cited page text; failures are treated as dead."""

    def __init__(
        self,
        timeout: float = 8.0,
        max_chars: int = 20_000,
        enabled: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout = timeout
        self.max_chars = max_chars
        self._cache: dict[str, str | None] = {}
        self._client = client

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True, timeout=self.timeout, headers={"User-Agent": _UA}
            )
        return self._client

    def fetch(self, url: str) -> str | None:
        """Return extracted page text, or None if the page is dead/unreachable/empty."""
        if url in self._cache:
            return self._cache[url]
        text = self._do_fetch(url)
        self._cache[url] = text
        return text

    @staticmethod
    def _fetchable_url(url: str) -> str:
        """Map a URL to a server-rendered variant our simple client can read.

        reddit's `www.`/`np.` pages serve a JS app shell (no thread text) to a
        non-browser client, while `old.reddit.com` server-renders the full
        comment tree as plain HTML. We rewrite only for the GET; the original URL
        stays the cache key and the cited link (what the user clicks).
        """
        return re.sub(
            r"^(https?://)(?:www\.|np\.)?reddit\.com/",
            r"\1old.reddit.com/",
            url,
            count=1,
            flags=re.IGNORECASE,
        )

    def _do_fetch(self, url: str) -> str | None:
        client = self._ensure_client()
        try:
            resp = client.get(self._fetchable_url(url))
            if resp.status_code in (404, 410) or resp.status_code >= 500:
                return None
            text = html_to_text(resp.text)[: self.max_chars]
            return text or None
        except Exception:
            return None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
