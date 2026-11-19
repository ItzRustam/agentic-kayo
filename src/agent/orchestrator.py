"""Bounded manual tool-calling agent orchestrator without LangGraph."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

from src.config import AppConfig, get_config
from src.tools.registry import ToolRegistry, default_registry

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    pending_action: dict[str, Any] | None = None
    messages: list[BaseMessage] = field(default_factory=list)
    error: str | None = None


class AgentOrchestrator:
    """
    Manual, bounded tool-calling loop.
    Controls the interaction between user messages, primary Gemini LLM,
    and the tool execution layer.
    """

    def __init__(
        self,
        model: BaseChatModel,
        registry: ToolRegistry | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.registry = registry or default_registry
        self.raw_model = model
        # Bind registry tools to the model
        lc_tools = self.registry.get_langchain_tools()
        self.bound_model = model.bind_tools(lc_tools) if lc_tools else model

    def run(
        self,
        messages: list[BaseMessage],
        on_step_callback: Callable[[str], None] | None = None,
    ) -> AgentRunResult:
        """
        Execute the bounded agent loop starting from the provided messages.
        """
        current_messages = list(messages)
        max_steps = self.config.max_agent_steps
        executed_tools_log: list[dict[str, Any]] = []

        for step in range(max_steps):
            logger.debug("Orchestrator loop iteration %d/%d", step + 1, max_steps)

            try:
                ai_response = self.bound_model.invoke(current_messages)
            except Exception as exc:
                logger.exception("LLM provider invocation failed: %s", exc)
                return AgentRunResult(
                    content="I encountered an error communicating with the model provider. Please check your API key and connection.",
                    tool_calls=executed_tools_log,
                    messages=current_messages,
                    error=str(exc),
                )

            # Check if model requested any tool calls
            tool_calls = getattr(ai_response, "tool_calls", None) or []

            if not tool_calls:
                # Model returned a final natural language response
                current_messages.append(ai_response)
                final_text = self._extract_content_text(ai_response.content)
                return AgentRunResult(
                    content=final_text,
                    tool_calls=executed_tools_log,
                    requires_confirmation=False,
                    messages=current_messages,
                )

            # Append the assistant's tool-calling message
            current_messages.append(ai_response)

            # Process each requested tool call
            for call in tool_calls:
                call_id = call.get("id", f"call_{step}")
                tool_name = call.get("name", "")
                tool_args = call.get("args") or {}

                if on_step_callback:
                    on_step_callback(f"Executing tool: {tool_name}...")

                # Dispatch tool
                result = self.registry.dispatch(
                    name=tool_name,
                    arguments=tool_args,
                    bypass_confirmation=False,
                )

                # Check if confirmation is required
                if result.get("requires_confirmation"):
                    logger.info("Tool '%s' requires confirmation. Halting loop for user approval.", tool_name)
                    return AgentRunResult(
                        content=result.get("message", f"Approval required for '{tool_name}'."),
                        tool_calls=executed_tools_log,
                        requires_confirmation=True,
                        pending_action={
                            "call_id": call_id,
                            "tool": tool_name,
                            "arguments": tool_args,
                            "preview": result.get("preview"),
                        },
                        messages=current_messages,
                    )

                executed_tools_log.append({
                    "call_id": call_id,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result,
                })

                # Append tool result message
                tool_msg = ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call_id,
                )
                current_messages.append(tool_msg)

        # Exceeded maximum tool steps
        logger.warning("Agent reached maximum step limit of %d", max_steps)
        notice = f"\n\n*[Notice: Agent stopped after reaching maximum allowed steps ({max_steps})]*"
        return AgentRunResult(
            content="I gathered some information but reached the maximum allowed tool execution steps." + notice,
            tool_calls=executed_tools_log,
            requires_confirmation=False,
            messages=current_messages,
            error="Maximum agent steps exceeded.",
        )

    def resume_action(
        self,
        messages: list[BaseMessage],
        pending_action: dict[str, Any],
        approved: bool,
        on_step_callback: Callable[[str], None] | None = None,
    ) -> AgentRunResult:
        """
        Resume the orchestrator loop after a user approves or rejects a pending tool action.
        """
        current_messages = list(messages)
        call_id = pending_action["call_id"]
        tool_name = pending_action["tool"]
        tool_args = pending_action["arguments"]

        if not approved:
            # User rejected the action
            rejected_result = {
                "ok": False,
                "tool": tool_name,
                "error": "Action was cancelled by the user in the interface.",
            }
            tool_msg = ToolMessage(
                content=json.dumps(rejected_result),
                tool_call_id=call_id,
            )
            current_messages.append(tool_msg)
        else:
            # User approved: execute with bypass_confirmation=True
            if on_step_callback:
                on_step_callback(f"Executing approved action: {tool_name}...")

            exec_result = self.registry.dispatch(
                name=tool_name,
                arguments=tool_args,
                bypass_confirmation=True,
            )
            tool_msg = ToolMessage(
                content=json.dumps(exec_result, ensure_ascii=False),
                tool_call_id=call_id,
            )
            current_messages.append(tool_msg)

        # Resume loop from current state
        return self.run(current_messages, on_step_callback=on_step_callback)

    @staticmethod
    def _extract_content_text(content: Any) -> str:
        """Helper to extract clean string from LLM message content."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return str(content)
