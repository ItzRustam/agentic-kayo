"""Tests for configuration loader."""

import os
import unittest
from unittest.mock import patch
from src.config import get_config, AppConfig


class TestConfig(unittest.TestCase):
    def test_default_config_values(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.kayo_model, "gemini-3.5-flash-lite")
            self.assertEqual(cfg.codegen_model, "baidu/ernie-5.5-flash-preview:free")
            self.assertEqual(cfg.vosk_model_path, "models/en-small")
            self.assertEqual(cfg.max_agent_steps, 8)
            self.assertEqual(cfg.smtp_port, 587)
            self.assertTrue(cfg.smtp_use_tls)
            self.assertEqual(cfg.app_timezone, "Asia/Kolkata")

    def test_validation_missing_keys(self):
        cfg = AppConfig(
            google_api_key="",
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
            cfg.validate_google_credentials()

        with self.assertRaises(ValueError):
            cfg.validate_openrouter_credentials()

    def test_validation_warnings(self):
        cfg = AppConfig(
            google_api_key="valid",
            openrouter_api_key="valid",
            kayo_model="gemini",
            codegen_model="ernie",
            vosk_model_path="models",
            max_agent_steps=-1,
            mail_password="",
            smtp_host="",
            smtp_port=99999,
            smtp_use_tls=True,
            app_timezone="UTC",
            kayo_workspace="./workspace",
            python_runner_url="http://localhost:8765",
        )
        issues = cfg.validate()
        self.assertEqual(len(issues), 2)


if __name__ == "__main__":
    unittest.main()
