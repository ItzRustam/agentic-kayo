"""Online Text-to-Speech engine using gTTS with in-memory MP3 generation."""

from __future__ import annotations

import io
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)


def text_to_speech_mp3(text: str, lang: str = "en", tld: str = "com") -> bytes | None:
    """
    Generate MP3 audio bytes from text using Google Translate TTS (gTTS).
    Returns MP3 bytes if successful, or None if network/generation fails.
    """
    clean_text = str(text).strip()
    if not clean_text:
        return None

    # Truncate very long text to avoid timeouts
    if len(clean_text) > 4000:
        clean_text = clean_text[:4000] + "..."

    try:
        tts = gTTS(text=clean_text, lang=lang, tld=tld, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()
    except Exception as exc:
        logger.warning("gTTS audio generation failed (network or provider error): %s", exc)
        return None
