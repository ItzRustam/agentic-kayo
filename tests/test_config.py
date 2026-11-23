import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../src")

import unittest
from unittest.mock import patch, mock_open
from src.config_loader import get_configs, load_user_info
import json
from dotenv import load_dotenv



class TestConfigLoader(unittest.TestCase):

    @patch('config_loader.load_dotenv')
    def test_get_configs_with_env_vars(self, mock_load_dotenv):
        """Test that configs load correctly from environment variables"""
        # Setup test environment variables
        test_env = {
            "OPENROUTER_API_KEY": "test_api_key",
            "MODEL": "test_model",
            "VOSK_MODEL_PATH": "test_model_path",
            "MAX_AGENT_STEPS": "15",
        }

        for key, value in test_env.items():
            os.environ[key] = value

        # Call function
        result = get_configs()

        # Verify results
        self.assertEqual(result["api_key"], "test_api_key")
        self.assertEqual(result["model"], "test_model")
        self.assertEqual(result["vosk_model"], "test_model_path")
        self.assertEqual(result["max_agent_steps"], 15)  # Converted to bool

    @patch('config_loader.load_dotenv')
    def test_get_configs_with_defaults(self, mock_load_dotenv):
        """Test that configs return defaults when environment variables are missing"""
        # Clear environment variables
        for key in os.environ:
            if key.startswith("OPENROUTER_API_KEY"):
                del os.environ[key]

        # Call function
        result = get_configs()

        # Verify defaults
        self.assertEqual(result["api_key"], "")
        self.assertEqual(result["model"], "baidu/ernie-5.5-flash-preview:free")
        self.assertEqual(result["vosk_model"], "models/en-small")
        self.assertEqual(result["max_agent_steps"], 12)

    def test_configs_returns_copy(self):
        """Test that configs returns a copy to prevent modification"""
        original = get_configs()
        original["api_key"] = "modified"

        # Verify original wasn't modified
        self.assertEqual(get_configs()["api_key"], "")

if __name__ == '__main__':
    unittest.main()