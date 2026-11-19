"""Microphone capture helper for Streamlit browser audio."""

from __future__ import annotations

import io
import logging
from typing import Any

from src.voice.stt import transcribe_wav_bytes

logger = logging.getLogger(__name__)


def process_browser_audio(audio_file_or_bytes: Any) -> str:
    """
    Process audio received from Streamlit's st.audio_input component and transcribe with Vosk.
    """
    if audio_file_or_bytes is None:
        return ""

    try:
        if isinstance(audio_file_or_bytes, bytes):
            raw_bytes = audio_file_or_bytes
        elif hasattr(audio_file_or_bytes, "read"):
            audio_file_or_bytes.seek(0)
            raw_bytes = audio_file_or_bytes.read()
        elif hasattr(audio_file_or_bytes, "getvalue"):
            raw_bytes = audio_file_or_bytes.getvalue()
        else:
            logger.warning("Unsupported audio object type: %s", type(audio_file_or_bytes))
            return ""

        return transcribe_wav_bytes(raw_bytes)
    except Exception as exc:
        logger.error("Failed to process browser audio: %s", exc)
        return ""
