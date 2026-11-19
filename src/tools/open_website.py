"""URL validation and client-side website link tool."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)

FORBIDDEN_SCHEMES = {"file", "javascript", "data", "vbscript", "about"}


def open_website(url: str) -> dict[str, Any]:
    """
    Validate a selected HTTP/HTTPS URL and return it to the UI as a clickable link.
    Rejects unsafe protocols, malformed URLs, and URLs with embedded credentials.
    """
    raw_url = str(url).strip()
    if not raw_url:
        return {
            "ok": False,
            "tool": "open_website",
            "error": "URL cannot be empty.",
        }

    try:
        parsed = urllib.parse.urlparse(raw_url)
    except Exception as exc:
        return {
            "ok": False,
            "tool": "open_website",
            "error": f"Malformed URL: {exc}",
        }

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return {
            "ok": False,
            "tool": "open_website",
            "error": f"Invalid scheme '{scheme}'. Only HTTP and HTTPS URLs are permitted.",
        }

    if not parsed.netloc or not parsed.hostname:
        return {
            "ok": False,
            "tool": "open_website",
            "error": "URL must contain a valid hostname.",
        }

    # Reject embedded credentials (username:password@domain)
    if parsed.username or parsed.password:
        return {
            "ok": False,
            "tool": "open_website",
            "error": "URLs containing embedded credentials are not allowed for security reasons.",
        }

    # Sanitized safe URL
    safe_url = urllib.parse.urlunparse(parsed)

    return {
        "ok": True,
        "tool": "open_website",
        "result": {
            "url": safe_url,
            "hostname": parsed.hostname,
            "message": f"Website link verified: {safe_url}",
        },
    }
