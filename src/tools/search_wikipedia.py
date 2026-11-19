"""Wikipedia search tool returning concise summary only."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

USER_AGENT = "AgenticKayo/1.0 (https://github.com/agentic-kayo; mailto:contact@example.com)"


def search_wikipedia(query: str) -> dict[str, Any]:
    """
    Search Wikipedia and return ONLY a concise article summary, title, and canonical page URL.
    Never returns full article text.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "ok": False,
            "tool": "search_wikipedia",
            "error": "Query cannot be empty.",
        }

    try:
        # Step 1: Opensearch to find canonical article title
        encoded_search = urllib.parse.quote_plus(cleaned_query)
        search_url = (
            f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_search}"
            f"&limit=3&namespace=0&format=json"
        )
        req = urllib.request.Request(search_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Format: [query, [titles], [descriptions], [urls]]
        if not data or len(data) < 4 or not data[1]:
            return {
                "ok": False,
                "tool": "search_wikipedia",
                "error": f"No Wikipedia article found for '{cleaned_query}'.",
            }

        matched_title = data[1][0]
        canonical_url = data[3][0]

        # Step 2: Fetch concise summary via REST API
        encoded_title = urllib.parse.quote(matched_title.replace(" ", "_"))
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        summary_req = urllib.request.Request(summary_url, headers={"User-Agent": USER_AGENT})

        with urllib.request.urlopen(summary_req, timeout=10) as resp:
            summary_data = json.loads(resp.read().decode("utf-8"))

        extract_type = summary_data.get("type", "")
        if extract_type == "disambiguation":
            return {
                "ok": True,
                "tool": "search_wikipedia",
                "result": {
                    "title": matched_title,
                    "url": canonical_url,
                    "summary": (
                        f"The topic '{matched_title}' is ambiguous on Wikipedia. "
                        f"Possible matches: {', '.join(data[1][:5])}. Please specify your query."
                    ),
                    "is_disambiguation": True,
                },
            }

        extract = summary_data.get("extract", "").strip()
        if not extract and len(data[2]) > 0:
            extract = data[2][0]

        return {
            "ok": True,
            "tool": "search_wikipedia",
            "result": {
                "title": summary_data.get("title", matched_title),
                "url": summary_data.get("content_urls", {}).get("desktop", {}).get("page", canonical_url),
                "summary": extract or "No summary extract available.",
                "description": summary_data.get("description", ""),
            },
        }

    except urllib.error.HTTPError as http_err:
        if http_err.code == 404:
            return {
                "ok": False,
                "tool": "search_wikipedia",
                "error": f"Article not found on Wikipedia for '{cleaned_query}'.",
            }
        return {
            "ok": False,
            "tool": "search_wikipedia",
            "error": f"Wikipedia HTTP error: {http_err.code}",
        }
    except Exception as exc:
        logger.warning("search_wikipedia error for query '%s': %s", cleaned_query, exc)
        return {
            "ok": False,
            "tool": "search_wikipedia",
            "error": f"Wikipedia lookup failed: {str(exc)}",
        }
