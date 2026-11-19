"""Tests for agent orchestrator and bounded tool execution loop."""

import unittest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.orchestrator import AgentOrchestrator
from src.config import AppConfig
from src.tools.registry import ToolRegistry


class TestAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            google_api_key="fake-key",
            openrouter_api_key="fake-key",
            kayo_model="gemini",
            codegen_model="ernie",
            vosk_model_path="models/en-small",
            max_agent_steps=3,
            mail_password="",
            smtp_host="",
            smtp_port=587,
            smtp_use_tls=True,
            app_timezone="UTC",
            kayo_workspace="./workspace",
            python_runner_url="http://localhost:8765",
        )
        self.registry = ToolRegistry()
        self.mock_model = MagicMock()
        self.mock_bound_model = MagicMock()
        self.mock_model.bind_tools.return_value = self.mock_bound_model

    def test_direct_assistant_response_no_tools(self):
        self.mock_bound_model.invoke.return_value = AIMessage(content="Hello! How can I help you today?")
        orchestrator = AgentOrchestrator(self.mock_model, self.registry, self.config)

        messages = [HumanMessage(content="Hi")]
        result = orchestrator.run(messages)

        self.assertFalse(result.requires_confirmation)
        self.assertEqual(result.content, "Hello! How can I help you today?")
        self.assertEqual(len(result.tool_calls), 0)

    def test_single_tool_call_loop(self):
        # Step 1: Model requests calculation
        calc_call = {
            "name": "calculate",
            "args": {"expression": "100 / 4"},
            "id": "call_1",
            "type": "tool_call",
        }
        step1_response = AIMessage(content="", tool_calls=[calc_call])
        # Step 2: Model gives final answer
        step2_response = AIMessage(content="100 divided by 4 is 25.")

        self.mock_bound_model.invoke.side_effect = [step1_response, step2_response]
        orchestrator = AgentOrchestrator(self.mock_model, self.registry, self.config)

        messages = [HumanMessage(content="What is 100 / 4?")]
        result = orchestrator.run(messages)

        self.assertEqual(result.content, "100 divided by 4 is 25.")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0]["tool"], "calculate")
        self.assertEqual(result.tool_calls[0]["result"]["result"]["value"], 25.0)

    def test_confirmation_gating_pauses_loop(self):
        # Model requests delete_file
        del_call = {
            "name": "delete_file",
            "args": {"path": "test.txt"},
            "id": "call_del",
            "type": "tool_call",
        }
        step1_response = AIMessage(content="", tool_calls=[del_call])
        self.mock_bound_model.invoke.return_value = step1_response

        orchestrator = AgentOrchestrator(self.mock_model, self.registry, self.config)
        messages = [HumanMessage(content="Delete test.txt")]
        result = orchestrator.run(messages)

        self.assertTrue(result.requires_confirmation)
        self.assertIsNotNone(result.pending_action)
        self.assertEqual(result.pending_action["tool"], "delete_file")

    def test_resume_action_rejected(self):
        orchestrator = AgentOrchestrator(self.mock_model, self.registry, self.config)
        pending = {
            "call_id": "call_del",
            "tool": "delete_file",
            "arguments": {"path": "test.txt"},
        }
        messages = [HumanMessage(content="Delete file")]

        self.mock_bound_model.invoke.return_value = AIMessage(content="Understood, I will not delete the file.")
        result = orchestrator.resume_action(messages, pending, approved=False)

        self.assertFalse(result.requires_confirmation)
        self.assertEqual(result.content, "Understood, I will not delete the file.")

    def test_max_steps_exceeded(self):
        # Model loops calling tool endlessly
        calc_call = {
            "name": "calculate",
            "args": {"expression": "1 + 1"},
            "id": "call_loop",
            "type": "tool_call",
        }
        loop_msg = AIMessage(content="", tool_calls=[calc_call])
        self.mock_bound_model.invoke.return_value = loop_msg

        orchestrator = AgentOrchestrator(self.mock_model, self.registry, self.config)
        messages = [HumanMessage(content="Loop forever")]
        result = orchestrator.run(messages)

        self.assertIn("reached the maximum allowed tool execution steps", result.content)
        self.assertEqual(len(result.tool_calls), self.config.max_agent_steps)


if __name__ == "__main__":
    unittest.main()
