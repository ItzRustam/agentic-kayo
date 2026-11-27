"""Unit tests for Groq Whisper Large v3 Turbo Speech-to-Text module."""

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../src")

from src.voices.stt import (
    GROQ_WHISPER_MODEL,
    get_groq_client,
    transcribe_audio,
)


class TestGroqSTT(unittest.TestCase):
    def test_model_constant_is_whisper_large_v3_turbo(self):
        """Verify the exact Groq model required is whisper-large-v3-turbo."""
        self.assertEqual(GROQ_WHISPER_MODEL, "whisper-large-v3-turbo")

    def test_vosk_not_imported_in_stt(self):
        """Verify that Vosk is not imported in the active STT module."""
        import src.voices.stt as stt_module
        self.assertNotIn("vosk", sys.modules.get("src.voices.stt", {}).__dict__)
        self.assertFalse(hasattr(stt_module, "KaldiRecognizer"))
        self.assertFalse(hasattr(stt_module, "Model"))

    def test_get_groq_client_missing_key(self):
        """get_groq_client returns None when no API key is configured."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            client = get_groq_client(api_key="")
            self.assertIsNone(client)

    def test_get_groq_client_with_key(self):
        """get_groq_client initializes client when key is provided."""
        client = get_groq_client(api_key="gsk_test_fake_api_key_12345")
        self.assertIsNotNone(client)

    def test_transcribe_audio_empty_inputs(self):
        """transcribe_audio returns empty string for None or empty/short bytes."""
        self.assertEqual(transcribe_audio(None), "")
        self.assertEqual(transcribe_audio(b""), "")
        self.assertEqual(transcribe_audio(b"too_short"), "")

    @patch("src.voices.stt.get_groq_client")
    def test_transcribe_audio_success_string_response(self, mock_get_client):
        """Verify transcription call with expected parameters and string return."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "  Hello, this is a test.  "
        mock_get_client.return_value = mock_client

        # Sample audio bytes > 100 bytes
        fake_audio = b"RIFF" + b"\x00" * 200

        result = transcribe_audio(fake_audio, api_key="gsk_test")
        self.assertEqual(result, "Hello, this is a test.")

        mock_client.audio.transcriptions.create.assert_called_once_with(
            file=("recording.wav", fake_audio),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
            temperature=0.0,
            timeout=30.0,
        )

    @patch("src.voices.stt.get_groq_client")
    def test_transcribe_audio_file_like_object(self, mock_get_client):
        """Verify transcription with BytesIO object."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "Transcription from BytesIO"
        mock_get_client.return_value = mock_client

        fake_audio = b"RIFF" + b"\x00" * 200
        buf = io.BytesIO(fake_audio)
        buf.name = "microphone_input.wav"

        result = transcribe_audio(buf, api_key="gsk_test")
        self.assertEqual(result, "Transcription from BytesIO")
        mock_client.audio.transcriptions.create.assert_called_once_with(
            file=("microphone_input.wav", fake_audio),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
            temperature=0.0,
            timeout=30.0,
        )

    @patch("src.voices.stt.get_groq_client")
    def test_transcribe_audio_error_handling(self, mock_get_client):
        """Verify that API errors or timeouts do not crash the application."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("Groq rate limit or connection timeout")
        mock_get_client.return_value = mock_client

        fake_audio = b"RIFF" + b"\x00" * 200
        result = transcribe_audio(fake_audio, api_key="gsk_test")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
