"""Unit tests for offline Vosk Speech-to-Text module."""

import io
import os
import sys
import unittest
import wave
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../src")

from src.voices.stt import (
    convert_audio_to_pcm,
    get_vosk_model,
    transcribe_audio,
)


class TestVoskSTT(unittest.TestCase):
    def test_convert_audio_empty(self):
        self.assertEqual(convert_audio_to_pcm(b""), b"")

    def test_convert_audio_valid_wav(self):
        # Create 16kHz mono 16-bit WAV
        rate = 16000
        samples = np.zeros(1600, dtype=np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(samples.tobytes())
        wav_bytes = buf.getvalue()

        pcm = convert_audio_to_pcm(wav_bytes)
        self.assertEqual(len(pcm), len(samples.tobytes()))

    def test_convert_audio_stereo_and_resampling(self):
        # Create 44.1kHz stereo 16-bit WAV
        rate = 44100
        samples = np.zeros((4410, 2), dtype=np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(samples.tobytes())
        wav_bytes = buf.getvalue()

        pcm = convert_audio_to_pcm(wav_bytes)
        # Should be resampled to 16kHz (around 1600 samples * 2 bytes = 3200 bytes)
        self.assertTrue(len(pcm) > 0)
        self.assertEqual(len(pcm) % 2, 0)

    def test_get_vosk_model_invalid_path(self):
        model = get_vosk_model("/nonexistent/path/to/vosk")
        self.assertIsNone(model)

    def test_transcribe_audio_empty_or_none(self):
        self.assertEqual(transcribe_audio(None), "")
        self.assertEqual(transcribe_audio(b""), "")

    def test_get_vosk_model_valid(self):
        # Check if local model exists
        if os.path.exists("models/en-small"):
            model = get_vosk_model("models/en-small")
            self.assertIsNotNone(model)


if __name__ == "__main__":
    unittest.main()
