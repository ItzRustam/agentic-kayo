"""Web search tool using DuckDuckGo public search with structured results."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_SNIPPET_LENGTH = 300


def _clean_text(html_text: str) -> str:
    """Strip HTML tags and clean up whitespace."""
    text = re.sub(r"<[^>]+>", "", html_text)
    text = urllib.parse.unquote(text)
    text = " ".join(text.split())
    return text


def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Search the web for a query and return concise, structured results.
    Each result contains title, url, snippet, and optional publication date.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "ok": False,
            "tool": "web_search",
            "error": "Search query cannot be empty.",
        }

    capped_results = min(max(1, max_results), 10)

    try:
        encoded_query = urllib.parse.quote_plus(cleaned_query)
        # Using DuckDuckGo HTML endpoint
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Parse results from HTML
        results: list[dict[str, str]] = []
        # Find result snippets in DuckDuckGo HTML output
        pattern = re.compile(
            r'<a class="result__url" href="(?P<url>[^"]+)".*?>.*?</a>.*?'
            r'<a class="result__snippet[^"]*" href="[^"]*">(?P<snippet>.*?)</a>',
            re.DOTALL,
        )
        title_pattern = re.compile(
            r'<h2 class="result__title">.*?<a class="result__a" href="(?P<url>[^"]+)">(?P<title>.*?)</a>',
            re.DOTALL,
        )

        titles_urls = title_pattern.findall(html)
        snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)

        for i, (u, t) in enumerate(titles_urls[:capped_results]):
            # Unescape actual target URL if it is a DDG redirect
            actual_url = u
            if "uddg=" in u:
                m = re.search(r'uddg=([^&]+)', u)
                if m:
                    actual_url = urllib.parse.unquote(m.group(1))

            snippet = ""
            if i < len(snippets):
                snippet = _clean_text(snippets[i])
                if len(snippet) > MAX_SNIPPET_LENGTH:
                    snippet = snippet[:MAX_SNIPPET_LENGTH] + "..."

            results.append({
                "title": _clean_text(t),
                "url": actual_url,
                "snippet": snippet,
                "date": "",
            })

        if not results:
            # Fallback attempt with DuckDuckGo Lite if HTML gave 0 items
            lite_url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
            lite_req = urllib.request.Request(lite_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(lite_req, timeout=10) as resp:
                lite_html = resp.read().decode("utf-8", errors="replace")

            lite_links = re.findall(r'<a class="result-link" href="([^"]+)">(.*?)</a>', lite_html, re.DOTALL)
            lite_snippets = re.findall(r'<td class="result-snippet">(.*?)</td>', lite_html, re.DOTALL)
            for i, (u, t) in enumerate(lite_links[:capped_results]):
                snippet = ""
                if i < len(lite_snippets):
                    snippet = _clean_text(lite_snippets[i])
                    if len(snippet) > MAX_SNIPPET_LENGTH:
                        snippet = snippet[:MAX_SNIPPET_LENGTH] + "..."
                results.append({
                    "title": _clean_text(t),
                    "url": u,
                    "snippet": snippet,
                    "date": "",
                })

        return {
            "ok": True,
            "tool": "web_search",
            "result": results,
            "total_found": len(results),
        }

    except Exception as exc:
        logger.warning("web_search error for query '%s': %s", cleaned_query, exc)
        return {
            "ok": False,
            "tool": "web_search",
            "error": f"Search failed: {str(exc)}",
        }
