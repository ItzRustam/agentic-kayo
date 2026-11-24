"""Offline Speech-to-Text module using Vosk."""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import wave
from typing import Any

import numpy as np
from vosk import KaldiRecognizer, Model

from src.config_loader import get_configs

logger = logging.getLogger(__name__)

# Module-level cache so the Vosk model is loaded only once per process
_MODEL_CACHE: dict[str, Model] = {}


def get_vosk_model(model_path: str | None = None) -> Model | None:
    """Load or retrieve the cached Vosk speech recognition model."""
    target_path = model_path or get_configs().get("vosk_model") or os.getenv("VOSK_MODEL_PATH", "models/en-small")
    resolved_path = os.path.abspath(target_path)

    if resolved_path in _MODEL_CACHE:
        return _MODEL_CACHE[resolved_path]

    if not os.path.exists(resolved_path):
        # Check relative path
        if os.path.exists(target_path):
            resolved_path = os.path.abspath(target_path)
        else:
            logger.error("Vosk model directory not found at '%s' (resolved: '%s').", target_path, resolved_path)
            return None

    try:
        logger.info("Loading Vosk speech model from: %s", resolved_path)
        model = Model(resolved_path)
        _MODEL_CACHE[resolved_path] = model
        return model
    except Exception as exc:
        logger.error("Failed to initialize Vosk model from '%s': %s", resolved_path, exc)
        return None


def convert_audio_to_pcm(audio_bytes: bytes) -> bytes:
    """
    Convert incoming audio bytes to 16 kHz, 16-bit, mono PCM.
    First tries Python's standard wave module with numpy; falls back to ffmpeg if needed.
    """
    if not audio_bytes:
        return b""

    # Attempt 1: Standard wave parsing (WAV input from browser or memory)
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if raw_frames:
            # Map sample width to numpy dtype
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            elif sample_width == 1:
                dtype = np.int8
            else:
                dtype = np.int16

            audio_arr = np.frombuffer(raw_frames, dtype=dtype)

            # Convert multi-channel to mono by averaging channels
            if channels > 1:
                audio_arr = audio_arr.reshape(-1, channels).mean(axis=1)

            # Normalize to int16
            if dtype == np.int32:
                audio_arr = (audio_arr / 65536).astype(np.int16)
            elif dtype == np.int8:
                audio_arr = (audio_arr * 256).astype(np.int16)
            else:
                audio_arr = audio_arr.astype(np.int16)

            # Resample to 16,000 Hz if needed
            target_rate = 16000
            if framerate != target_rate and len(audio_arr) > 0:
                target_len = int(len(audio_arr) * target_rate / framerate)
                if target_len > 0:
                    audio_arr = np.interp(
                        np.linspace(0, len(audio_arr), target_len, endpoint=False),
                        np.arange(len(audio_arr)),
                        audio_arr,
                    ).astype(np.int16)

            return audio_arr.tobytes()
    except Exception as e:
        logger.debug("Native wave parsing not applicable: %s. Trying ffmpeg fallback.", e)

    # Attempt 2: FFmpeg fallback (handles WebM, OGG, MP4, etc. from browser)
    if shutil.which("ffmpeg"):
        try:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-f",
                    "s16le",
                    "-acodec",
                    "pcm_s16le",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "pipe:1",
                ],
                input=audio_bytes,
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception as ffmpeg_err:
            logger.warning("FFmpeg conversion failed: %s", ffmpeg_err)

    return b""


def transcribe_audio(
    audio_input: bytes | io.BytesIO | Any,
    model_path: str | None = None,
) -> str:
    """
    Transcribe audio recorded from the browser using Vosk.
    Returns the recognized text string, or empty string if unsuccessful or empty.
    """
    if audio_input is None:
        return ""

    try:
        if isinstance(audio_input, bytes):
            raw_bytes = audio_input
        elif hasattr(audio_input, "getvalue"):
            raw_bytes = audio_input.getvalue()
        elif hasattr(audio_input, "read"):
            audio_input.seek(0)
            raw_bytes = audio_input.read()
        else:
            return ""

        if not raw_bytes:
            return ""

        pcm_data = convert_audio_to_pcm(raw_bytes)
        if not pcm_data:
            logger.warning("No PCM audio data recovered from input.")
            return ""

        model = get_vosk_model(model_path)
        if model is None:
            logger.error("Vosk model could not be loaded. Transcription aborted.")
            return ""

        recognizer = KaldiRecognizer(model, 16000)
        recognizer.SetWords(False)

        chunk_size = 4000
        for i in range(0, len(pcm_data), chunk_size):
            recognizer.AcceptWaveform(pcm_data[i : i + chunk_size])

        final_res = json.loads(recognizer.FinalResult())
        transcript = final_res.get("text", "").strip()
        return transcript

    except Exception as exc:
        logger.error("Transcription error: %s", exc)
        return ""
