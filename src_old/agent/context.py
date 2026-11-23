"""Conversation context and message history builder."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src_old.agent.prompts import build_system_prompt
from src_old.storage.user_info import load_user_info


def build_initial_messages(
    history: list[dict[str, Any]] | None = None,
    profile_data: dict[str, Any] | None = None,
) -> list[BaseMessage]:
    """
    Assemble the complete LangChain message list including dynamic system prompt
    and past conversation turns.
    """
    profile = profile_data or load_user_info()
    system_prompt = build_system_prompt(profile)

    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    if not history:
        return messages

    for item in history:
        role = item.get("role", "")
        content = item.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = item.get("tool_calls")
            if tool_calls:
                messages.append(AIMessage(content=content or "", tool_calls=tool_calls))
            else:
                messages.append(AIMessage(content=content))
        elif role == "tool":
            tool_call_id = item.get("tool_call_id", "")
            messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))

    return messages
