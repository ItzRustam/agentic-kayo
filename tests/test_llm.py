import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../src")

import unittest
from unittest.mock import patch, mock_open
from src.llm import get_model
from langchain_openrouter import ChatOpenRouter

class TestLLM(unittest.TestCase):
    def test_return_type(self):
        """Test Model type to OpenRouter"""

        model = get_model()

        self.assertIsInstance(model, ChatOpenRouter)
