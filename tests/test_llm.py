"""Tests for LLM factory and codegen service."""

import unittest
from unittest.mock import MagicMock, patch
from src.config import AppConfig
from src.llm.factory import get_primary_model, get_codegen_model
from src.llm.codegen import generate_code


class TestLLMFactory(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            google_api_key="test-google-key",
            openrouter_api_key="test-openrouter-key",
            kayo_model="gemini-3.5-flash-lite",
            codegen_model="baidu/ernie-5.5-flash-preview:free",
            vosk_model_path="models/en-small",
            max_agent_steps=8,
            mail_password="",
            smtp_host="",
            smtp_port=587,
            smtp_use_tls=True,
            app_timezone="Asia/Kolkata",
            kayo_workspace="./workspace",
            python_runner_url="http://localhost:8765",
        )

    def test_missing_google_key_raises(self):
        bad_config = AppConfig(
            google_api_key="",
            openrouter_api_key="test",
            kayo_model="gemini",
            codegen_model="ernie",
            vosk_model_path="models",
            max_agent_steps=8,
            mail_password="",
            smtp_host="",
            smtp_port=587,
            smtp_use_tls=True,
            app_timezone="UTC",
            kayo_workspace="./workspace",
            python_runner_url="http://localhost:8765",
        )
        with self.assertRaises(ValueError):
            get_primary_model(bad_config)

    def test_missing_openrouter_key_raises(self):
        bad_config = AppConfig(
            google_api_key="test",
            openrouter_api_key="",
            kayo_model="gemini",
            codegen_model="ernie",
            vosk_model_path="models",
            max_agent_steps=8,
            mail_password="",
            smtp_host="",
            smtp_port=587,
            smtp_use_tls=True,
            app_timezone="UTC",
            kayo_workspace="./workspace",
            python_runner_url="http://localhost:8765",
        )
        with self.assertRaises(ValueError):
            get_codegen_model(bad_config)

    def test_primary_model_init(self):
        model = get_primary_model(self.config)
        self.assertEqual(model.model, "gemini-3.5-flash-lite")

    def test_codegen_model_init(self):
        model = get_codegen_model(self.config)
        self.assertEqual(model.model, "baidu/ernie-5.5-flash-preview:free")

    @patch("src.llm.codegen.get_codegen_model")
    def test_generate_code(self, mock_get_codegen):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "def add(a, b): return a + b"
        mock_model.invoke.return_value = mock_response
        mock_get_codegen.return_value = mock_model

        code = generate_code("write add function", language="python", config=self.config)
        self.assertIn("def add", code)
        mock_model.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
