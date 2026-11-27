"""Unit tests for Edge TTS Text-to-Speech module."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../src")

from src.voices.tts import (
    generate_audio_bytes,
    speak,
    text_to_speech,
)


class TestEdgeTTS(unittest.TestCase):
    def test_empty_text_returns_none(self):
        self.assertIsNone(text_to_speech(""))
        self.assertIsNone(text_to_speech("   "))

    @patch("src.voices.tts.edge_tts.Communicate")
    def test_text_to_speech_mocked(self, mock_comm_cls):
        mock_comm = MagicMock()

        async def fake_stream():
            yield {"type": "audio", "data": b"fake_mp3_chunk_1"}
            yield {"type": "audio", "data": b"fake_mp3_chunk_2"}

        mock_comm.stream.return_value = fake_stream()
        mock_comm_cls.return_value = mock_comm

        result = text_to_speech("Hello Kayo")
        self.assertEqual(result, b"fake_mp3_chunk_1fake_mp3_chunk_2")

    @patch("src.voices.tts.edge_tts.Communicate")
    def test_text_to_speech_failure_handling(self, mock_comm_cls):
        mock_comm_cls.side_effect = Exception("Network offline")
        result = text_to_speech("Testing error handling")
        self.assertIsNone(result)

    def test_speak_empty(self):
        # Calling speak with empty text should do nothing and not raise
        speak("")
        speak("   ")


if __name__ == "__main__":
    unittest.main()
