"""Text-to-Speech module using Edge TTS."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import tempfile
from typing import Any

import edge_tts

logger = logging.getLogger(__name__)

VOICE = "en-US-GuyNeural"
RATE = "+30%"
PITCH = "-20Hz"


def _run_async(coro: Any) -> Any:
    """Safely execute an async coroutine across sync and async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


async def generate_audio(text: str, output_path: str) -> None:
    """Generate audio and save directly to output_path using Edge TTS."""
    clean_text = text.strip() if text else ""
    if not clean_text:
        return

    communicate = edge_tts.Communicate(
        text=clean_text,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    await communicate.save(output_path)


async def generate_audio_bytes(
    text: str,
    voice: str = VOICE,
    rate: str = RATE,
    pitch: str = PITCH,
) -> bytes | None:
    """Generate MP3 audio bytes in-memory for browser playback."""
    clean_text = text.strip() if text else ""
    if not clean_text:
        return None

    try:
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice,
            rate=rate,
            pitch=pitch,
        )
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])

        return bytes(audio_data) if audio_data else None
    except Exception as exc:
        logger.warning("Edge TTS audio generation failed: %s", exc)
        return None


def text_to_speech(text: str) -> bytes | None:
    """Synchronous helper that returns MP3 audio bytes for browser playback."""
    return _run_async(generate_audio_bytes(text))


def speak(text: str) -> None:
    """Optional local audio playback via pygame (used only when requested locally)."""
    if not text or not text.strip():
        return

    try:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as file:
            audio_path = file.name

        try:
            _run_async(generate_audio(text, audio_path))
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                clock.tick(20)
        finally:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Local pygame playback failed or unavailable: %s", exc)
