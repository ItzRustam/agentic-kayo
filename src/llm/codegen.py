"""Dedicated code generation service using OpenRouter."""

from __future__ import annotations

import logging
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import AppConfig
from src.llm.factory import get_codegen_model

logger = logging.getLogger(__name__)

CODEGEN_SYSTEM_PROMPT = """You are Agentic Kayo's dedicated code generation engine.
Your task is to write high-quality, production-ready, clean, secure, and well-structured code.
Only output the code or code with concise explanations as requested by the user.
Avoid boilerplate or unnecessary external dependencies unless specifically requested.
Target language: {language}
"""


def generate_code(
    prompt: str,
    language: str = "python",
    context: str | None = None,
    config: AppConfig | None = None,
) -> str:
    """
    Generate code using the dedicated OpenRouter coding model.
    """
    model = get_codegen_model(config)

    system_text = CODEGEN_SYSTEM_PROMPT.format(language=language)
    if context:
        system_text += f"\nAdditional Context:\n{context}"

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=prompt),
    ]

    response = model.invoke(messages)
    content = response.content
    if isinstance(content, list):
        # In case content blocks are returned
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)
