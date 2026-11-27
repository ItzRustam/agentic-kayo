"""Central configuration loader and validator for Agentic Kayo."""

from __future__ import annotations

import os
from dotenv import load_dotenv
from typing import Dict, Any
import json

# loading .env file
load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Retrieve configuration value from environment variables or Streamlit Secrets."""
    val = os.getenv(key, "").strip()
    if val:
        return val

    # Support Streamlit Cloud Secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            secret_val = str(st.secrets[key]).strip()
            if secret_val:
                return secret_val
    except Exception:
        pass

    return default


def get_configs() -> Dict[str, Any]:
    configs : Dict[str, Any] = {}

    # adding configurations
    configs["api_key"] = _get_secret("OPENROUTER_API_KEY", "")
    configs["groq_api_key"] = _get_secret("GROQ_API_KEY", "")
    configs["model"] = _get_secret("MODEL", "baidu/ernie-5.5-flash-preview:free")
    configs["vosk_model"] = _get_secret("VOSK_MODEL_PATH", "models/en-small")

    raw_steps = _get_secret("MAX_AGENT_STEPS", "12")
    try:
        configs["max_agent_steps"] = int(raw_steps)
    except (ValueError, TypeError):
        configs["max_agent_steps"] = 12

    return configs.copy()


def load_user_info() -> Dict[str, str]:
    with open("user_info.json", "r") as file:
        user_info : Dict[str, str] = json.load(file)

    if len(user_info["name"]) <= 2:
        user_info["name"] = "Unnamed"
    
    return user_info
