"""Vosk speech-to-text offline recognition engine."""

from __future__ import annotations

import io
import json
import logging
import os
import wave
from typing import Any

import numpy as np
from vosk import KaldiRecognizer, Model

from src_old.config import get_config

logger = logging.getLogger(__name__)

_CACHED_MODEL: Model | None = None
_CACHED_MODEL_PATH: str | None = None


def get_vosk_model(model_path: str | None = None) -> Model:
    """Load or retrieve cached Vosk speech recognition model."""
    global _CACHED_MODEL, _CACHED_MODEL_PATH

    target_path = model_path or get_config().vosk_model_path
    if not os.path.exists(target_path):
        raise FileNotFoundError(
            f"Vosk model directory not found at '{target_path}'. "
            "Please ensure the model is extracted at the configured path."
        )

    if _CACHED_MODEL is None or _CACHED_MODEL_PATH != target_path:
        logger.info("Loading Vosk model from: %s", target_path)
        _CACHED_MODEL = Model(target_path)
        _CACHED_MODEL_PATH = target_path

    return _CACHED_MODEL


def transcribe_wav_bytes(audio_bytes: bytes, model_path: str | None = None) -> str:
    """
    Transcribe WAV audio bytes using the offline Vosk speech recognizer.
    Normalizes channels and sample rate to mono 16kHz 16-bit PCM if needed.
    """
    if not audio_bytes:
        return ""

    try:
        model = get_vosk_model(model_path)
    except Exception as exc:
        logger.warning("Vosk model unavailable: %s", exc)
        return ""

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if not raw_frames:
            return ""

        # Interpret PCM samples
        if sample_width == 2:
            dtype = np.int16
        elif sample_width == 4:
            dtype = np.int32
        elif sample_width == 1:
            dtype = np.int8
        else:
            dtype = np.int16

        audio_arr = np.frombuffer(raw_frames, dtype=dtype)

        # Reshape for multi-channel and average to mono
        if channels > 1:
            audio_arr = audio_arr.reshape(-1, channels).mean(axis=1)

        # Convert to int16
        if dtype != np.int16:
            if dtype == np.int32:
                audio_arr = (audio_arr / 65536).astype(np.int16)
            elif dtype == np.int8:
                audio_arr = (audio_arr * 256).astype(np.int16)
            else:
                audio_arr = audio_arr.astype(np.int16)
        else:
            audio_arr = audio_arr.astype(np.int16)

        # Resample to 16 kHz if different
        target_rate = 16000
        if framerate != target_rate and len(audio_arr) > 0:
            target_len = int(len(audio_arr) * target_rate / framerate)
            if target_len > 0:
                audio_arr = np.interp(
                    np.linspace(0, len(audio_arr), target_len, endpoint=False),
                    np.arange(len(audio_arr)),
                    audio_arr,
                ).astype(np.int16)
            framerate = target_rate

        frames = audio_arr.tobytes()

        recognizer = KaldiRecognizer(model, framerate)
        recognizer.SetWords(False)

        chunk_size = 4000
        for i in range(0, len(frames), chunk_size):
            recognizer.AcceptWaveform(frames[i : i + chunk_size])

        final_res = json.loads(recognizer.FinalResult())
        transcript = final_res.get("text", "").strip()
        logger.info("Transcribed audio result: '%s'", transcript)
        return transcript

    except Exception as exc:
        logger.error("Error during Vosk transcription: %s", exc)
        return ""
