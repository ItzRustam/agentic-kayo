"""Factory for creating primary conversational and dedicated coding LLMs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openrouter import ChatOpenRouter

from src.config import AppConfig, get_config

logger = logging.getLogger(__name__)


def get_primary_model(config: AppConfig | None = None) -> BaseChatModel:
    """
    Initialize and return the primary conversational model (Google Gemini).
    Raises ValueError if GOOGLE_API_KEY is not configured.
    """
    cfg = config or get_config()
    cfg.validate_google_credentials()

    logger.info("Initializing primary model: %s", cfg.kayo_model)
    return ChatGoogleGenerativeAI(
        model=cfg.kayo_model,
        api_key=cfg.google_api_key,
        temperature=0.7,
    )


def get_codegen_model(config: AppConfig | None = None) -> BaseChatModel:
    """
    Initialize and return the dedicated coding model (OpenRouter).
    Raises ValueError if OPENROUTER_API_KEY is not configured.
    """
    cfg = config or get_config()
    cfg.validate_openrouter_credentials()

    logger.info("Initializing codegen model: %s", cfg.codegen_model)
    return ChatOpenRouter(
        model=cfg.codegen_model,
        api_key=cfg.openrouter_api_key,
        temperature=0.2,
    )
