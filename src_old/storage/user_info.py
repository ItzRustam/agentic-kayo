"""Storage helper for reading and updating user_info.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_USER_INFO_PATH = Path("user_info.json")

SAFE_DEFAULT_USER_INFO: dict[str, Any] = {
    "profile": {
        "name": "",
        "email": "",
    },
    "preferences": [],
    "context": {},
}

FORBIDDEN_SECRET_KEYS = {
    "password",
    "mail_password",
    "secret",
    "api_key",
    "google_api_key",
    "openrouter_api_key",
    "token",
}


def _strip_secrets(data: Any) -> Any:
    """Recursively strip any keys that might contain credentials."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in FORBIDDEN_SECRET_KEYS:
                logger.warning("Stripped sensitive field '%s' from user profile storage.", k)
                continue
            cleaned[k] = _strip_secrets(v)
        return cleaned
    elif isinstance(data, list):
        return [_strip_secrets(item) for item in data]
    return data


def load_user_info(path: str | Path | None = None) -> dict[str, Any]:
    """
    Load user profile from user_info.json.
    Returns safe default if file is missing, empty, or malformed.
    """
    target = Path(path) if path else DEFAULT_USER_INFO_PATH
    if not target.exists():
        logger.warning("User info file %s does not exist. Using default profile.", target)
        return json.loads(json.dumps(SAFE_DEFAULT_USER_INFO))

    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                logger.warning("User info file %s is empty. Using default profile.", target)
                return json.loads(json.dumps(SAFE_DEFAULT_USER_INFO))
            data = json.loads(content)
            if not isinstance(data, dict):
                logger.warning("User info file %s is not a JSON object. Using default profile.", target)
                return json.loads(json.dumps(SAFE_DEFAULT_USER_INFO))
            # Ensure minimal keys exist
            if "profile" not in data or not isinstance(data["profile"], dict):
                data["profile"] = {"name": "", "email": ""}
            if "preferences" not in data or not isinstance(data["preferences"], list):
                data["preferences"] = []
            if "context" not in data or not isinstance(data["context"], dict):
                data["context"] = {}
            return data
    except Exception as exc:
        logger.warning("Failed to load user info from %s: %s. Using default profile.", target, exc)
        return json.loads(json.dumps(SAFE_DEFAULT_USER_INFO))


def save_user_info(data: dict[str, Any], path: str | Path | None = None) -> None:
    """
    Save user profile to user_info.json.
    Validates dictionary structure and strips any accidental credentials.
    """
    if not isinstance(data, dict):
        raise ValueError("User info data must be a dictionary.")

    target = Path(path) if path else DEFAULT_USER_INFO_PATH
    safe_data = _strip_secrets(data)

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(safe_data, f, indent=2)


def update_profile_sender(
    name: str, email: str, path: str | Path | None = None
) -> dict[str, Any]:
    """
    Explicitly update sender display name and email address in user_info.json.
    Returns the updated profile data.
    """
    data = load_user_info(path)
    if "profile" not in data or not isinstance(data["profile"], dict):
        data["profile"] = {}
    data["profile"]["name"] = str(name).strip()
    data["profile"]["email"] = str(email).strip()
    save_user_info(data, path)
    return data
