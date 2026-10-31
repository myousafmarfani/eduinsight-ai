"""Tavily-powered educational resource search.

Never raises for expected failures (missing key, rate limits, network errors, empty results): it
returns a `ResourceSearchOutcome` whose `status`/`message` the UI can show. URLs and titles come
only from search results; nothing is invented, invalid URLs are dropped and duplicates removed.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from app.schemas.analysis import EducationalResource, ResourceType

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
_COURSE_HOSTS = ("khanacademy.org", "coursera.org", "edx.org", "udemy.com", "ocw.mit.edu", "futurelearn.com")
_PRACTICE_HINTS = ("past paper", "pastpaper", "practice", "worksheet", "questions", "mcq", "exercise")


class SearchStatus(str, Enum):
    OK = "ok"
    NO_API_KEY = "no_api_key"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    EMPTY = "empty"


@dataclass
class ResourceSearchOutcome:
    status: SearchStatus
    message: str = ""
    resources: list[EducationalResource] = field(default_factory=list)


def _default_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: float):
    import httpx

    return httpx.post(url, headers=headers, json=json, timeout=timeout)


def is_valid_url(url: str) -> bool:
    """http(s) URL with a dotted host name."""
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and "." in (parsed.hostname or "")


def normalize_url(url: str) -> str:
    """Dedup key: lower-case host without www, no fragment, tracking parameters removed."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_")])
    return f"{host}{parsed.path.rstrip('/')}" + (f"?{query}" if query else "")


def classify_resource(url: str, title: str, kind: str) -> ResourceType:
    host = (urlparse(url).hostname or "").lower()
    text = f"{url} {title}".lower()
    if "youtube.com" in host or "youtu.be" in host:
        return ResourceType.VIDEO
    if any(h in host for h in _COURSE_HOSTS) or "/course" in text:
        return ResourceType.COURSE
    if url.lower().split("?")[0].endswith(".pdf") or any(h in text for h in _PRACTICE_HINTS) or kind == "practice":
        return ResourceType.PRACTICE
    if host.endswith((".edu", ".gov")) or "docs." in host or "documentation" in text:
        return ResourceType.DOCUMENTATION
    return ResourceType.ARTICLE


def dedupe_resources(resources: list[EducationalResource]) -> list[EducationalResource]:
    seen: set[str] = set()
    unique = []
    for res in resources:
        key = normalize_url(res.url)
        if key not in seen:
            seen.add(key)
            unique.append(res)
    return unique


class ResourceSearcher:
    """Thin Tavily client. `post` is injectable so tests can simulate failures without network access."""

    def __init__(self, api_key: str, timeout: float = 20.0, post: Callable[..., Any] | None = None):
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        self._post = post or _default_post

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, subject: str, kind: str = "guide", max_results: int = 4,
               context: str = "") -> ResourceSearchOutcome:
        """Run one search. `kind` is 'video', 'practice' or 'guide'; `context` is e.g. 'AKU-EB HSSC 1'."""
        if not self.configured:
            return ResourceSearchOutcome(SearchStatus.NO_API_KEY, "Resource search is disabled: TAVILY_API_KEY is not set.")
        body: dict[str, Any] = {"query": query, "search_depth": "basic", "max_results": max_results}
        if kind == "video":
            body["include_domains"] = ["youtube.com"]
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = self._post(TAVILY_URL, headers=headers, json=body, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - network/timeouts of any kind
            logger.warning("Tavily request failed: %s", type(exc).__name__)
            return ResourceSearchOutcome(SearchStatus.FAILED, "The resource search service could not be reached.")

        status = getattr(response, "status_code", 0)
        if status in (401, 403):
            return ResourceSearchOutcome(SearchStatus.FAILED, "Tavily rejected the API key; check TAVILY_API_KEY.")
        if status in (429, 432, 433):
            return ResourceSearchOutcome(SearchStatus.RATE_LIMITED, "Tavily rate or usage limit reached; try again later.")
        if status != 200:
            return ResourceSearchOutcome(SearchStatus.FAILED, f"Resource search failed (HTTP {status}).")
        try:
            results = response.json().get("results", [])
        except Exception:  # noqa: BLE001
            return ResourceSearchOutcome(SearchStatus.FAILED, "Resource search returned an unreadable response.")

        resources: list[EducationalResource] = []
        for item in results or []:
            url = str(item.get("url") or "").strip()
            title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
            if not title or not is_valid_url(url):
                continue
            snippet = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
            resources.append(EducationalResource(
                title=title[:200], url=url, resource_type=classify_resource(url, title, kind),
                description=(snippet[:240] + ("..." if len(snippet) > 240 else "")) or "No description provided by the search result.",
                subject=subject,
                why_recommended=(f"Surfaced by a web search for \"{query}\"" + (f" ({context})" if context else "")
                                 + ". Check that it matches your syllabus before relying on it."),
                search_query=query))
        resources = dedupe_resources(resources)
        if not resources:
            return ResourceSearchOutcome(SearchStatus.EMPTY, f"No results for \"{query}\".")
        return ResourceSearchOutcome(SearchStatus.OK, "", resources)
