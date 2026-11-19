"""Tests for voice pipeline (Vosk STT and gTTS)."""

import io
import unittest
import wave
from unittest.mock import MagicMock, patch

from src.voice.microphone import process_browser_audio
from src.voice.stt import transcribe_wav_bytes
from src.voice.tts import text_to_speech_mp3


class TestVoicePipeline(unittest.TestCase):
    def test_tts_empty_text(self):
        self.assertIsNone(text_to_speech_mp3(""))
        self.assertIsNone(text_to_speech_mp3("   "))

    @patch("src.voice.tts.gTTS")
    def test_tts_success(self, mock_gtts_cls):
        mock_instance = MagicMock()
        def write_fake_bytes(fp):
            fp.write(b"fake_mp3_data")
        mock_instance.write_to_fp.side_effect = write_fake_bytes
        mock_gtts_cls.return_value = mock_instance

        audio = text_to_speech_mp3("Hello world")
        self.assertIsNotNone(audio)
        self.assertEqual(audio, b"fake_mp3_data")

    @patch("src.voice.tts.gTTS")
    def test_tts_network_failure(self, mock_gtts_cls):
        mock_gtts_cls.side_effect = Exception("Connection error")
        audio = text_to_speech_mp3("Hello world")
        self.assertIsNone(audio)

    def test_stt_empty_bytes(self):
        transcript = transcribe_wav_bytes(b"")
        self.assertEqual(transcript, "")

    def test_stt_invalid_model_path(self):
        transcript = transcribe_wav_bytes(b"dummy", model_path="/nonexistent/model")
        self.assertEqual(transcript, "")

    def test_microphone_none_input(self):
        self.assertEqual(process_browser_audio(None), "")

    @patch("src.voice.microphone.transcribe_wav_bytes")
    def test_microphone_bytes_input(self, mock_transcribe):
        mock_transcribe.return_value = "hello there"
        buf = io.BytesIO(b"fake_audio")
        res = process_browser_audio(buf)
        self.assertEqual(res, "hello there")
        mock_transcribe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
