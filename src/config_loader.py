"""Central configuration loader and validator for Agentic Kayo."""

from __future__ import annotations

import os
from dotenv import load_dotenv
from typing import Dict, Any
import json

# loading .env file
load_dotenv()

def get_configs() -> Dict[str, Any]:
    configs : Dict[str, Any] = {}

    # adding configurations
    configs["api_key"] = os.getenv("OPENROUTER_API_KEY", "").strip()
    configs["model"] = os.getenv("MODEL", "baidu/ernie-5.5-flash-preview:free").strip()
    configs["vosk_model"] = os.getenv("VOSK_MODEL_PATH", "models/en-small").strip()
    configs["max_agent_steps"] = int(os.getenv("MAX_AGENT_STEPS", "12").strip())

    return configs.copy()


def load_user_info() -> Dict[str, str]:
    with open("user_info.json", "r") as file:
        user_info : Dict[str, str] = json.load(file)

    if len(user_info["name"]) <= 2:
        user_info["name"] = "Unnamed"
    
    return user_info
