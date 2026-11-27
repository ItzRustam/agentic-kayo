"""Speech-to-Text module using Groq Whisper Large v3 Turbo."""

from __future__ import annotations

import io
import logging
from typing import Any

from groq import Groq

from src.config_loader import get_configs

logger = logging.getLogger(__name__)

# Exact Groq Whisper model required
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"


def get_groq_client(api_key: str | None = None) -> Groq | None:
    """Initialize and return the Groq client using configured API key."""
    key = api_key or get_configs().get("groq_api_key")
    if not key or not key.strip():
        logger.error("GROQ_API_KEY is not configured. Cannot initialize Groq client.")
        return None

    try:
        return Groq(api_key=key.strip())
    except Exception as exc:
        logger.error("Failed to initialize Groq client: %s", exc)
        return None


def transcribe_audio(
    audio_input: bytes | io.BytesIO | Any,
    api_key: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Transcribe audio recorded from the browser using Groq Whisper Large v3 Turbo.

    Args:
        audio_input: Raw audio bytes or file-like object from Streamlit audio_input.
        api_key: Optional Groq API key override.

    Returns:
        Clean transcribed text string, or empty string if input is empty or error occurs.
    """
    if audio_input is None:
        return ""

    try:
        if isinstance(audio_input, bytes):
            raw_bytes = audio_input
            filename = "recording.wav"
        elif hasattr(audio_input, "getvalue"):
            raw_bytes = audio_input.getvalue()
            filename = getattr(audio_input, "name", "recording.wav") or "recording.wav"
        elif hasattr(audio_input, "read"):
            audio_input.seek(0)
            raw_bytes = audio_input.read()
            filename = getattr(audio_input, "name", "recording.wav") or "recording.wav"
        else:
            logger.warning("Unsupported audio input type: %s", type(audio_input))
            return ""

        if not raw_bytes or len(raw_bytes) < 100:
            logger.debug("Audio input is empty or too short (%d bytes).", len(raw_bytes) if raw_bytes else 0)
            return ""

        client = get_groq_client(api_key=api_key)
        if client is None:
            logger.error("Groq client could not be initialized (missing or invalid API key).")
            return ""

        result = client.audio.transcriptions.create(
            file=(filename, raw_bytes),
            model=GROQ_WHISPER_MODEL,
            language="en",
            response_format="text",
            temperature=0.0,
            timeout=30.0,
        )

        if isinstance(result, str):
            transcription = result.strip()
        elif hasattr(result, "text"):
            transcription = str(result.text).strip()
        else:
            transcription = str(result).strip()

        return transcription

    except Exception as exc:
        # Never log or expose API keys
        logger.error("Groq Whisper transcription failed: %s", exc)
        return ""
