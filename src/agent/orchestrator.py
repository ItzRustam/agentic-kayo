"""Combination of tools and LLM from factory, TL;DR Building Agent"""

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.exceptions import ModelRateLimitError

from src.llm import get_model
from src.tools import (
    web_search,
    search_arxiv,
    search_wikipedia,
    open_website,
    run_command,
    calculate,
    update_user_info,
    TOOLS_BOARD
)
from src.agent.prompts import system_prompt
from src.config_loader import get_configs


MAX_TOOL_CALL = int(get_configs()["max_agent_steps"])


def create_kayo():
    """Function to create Agent (Combined with Imported tools)"""
    llm = get_model()

    tools = [
        web_search,
        search_wikipedia,
        search_arxiv,
        open_website,
        run_command,
        calculate,
        update_user_info
    ]

    agent = llm.bind_tools(tools=tools)

    return agent


def run_kayo(query: str | None = None) -> str:
    """Run Kayo
    Function to invoke Kayo for response on given `query`
    """

    if not query or not query.strip():
        return "Query can't be None or Empty"

    # Message History will only last for given query to save memory
    message = []  # Always be reinitialized on each query as input

    message.append(system_prompt)
    message.append(HumanMessage(content=query))

    kayo = create_kayo()

    # ReAct Work
    try:
        result = kayo.invoke(message)
        message.append(result)

        tool_calls = 0

        while result.tool_calls:

            if tool_calls >= MAX_TOOL_CALL:
                return (
                    "Okay, I've done enough digging for now. "
                    "I'm hitting my tool limit—let's try a smaller request."
                )

            # Multi-tool calling
            for tool_info in result.tool_calls:

                if tool_calls >= MAX_TOOL_CALL:
                    return (
                        "Okay, I've done enough digging for now. "
                        "I'm hitting my tool limit—let's try a smaller request."
                    )

                chosen_tool = TOOLS_BOARD[tool_info["name"]]

                try:
                    tool_result = chosen_tool.invoke(tool_info["args"])

                except Exception as E:
                    tool_result = f"Tool execution failed: {str(E)}"

                tool_result = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_info["id"]
                )

                message.append(tool_result)

                tool_calls += 1

            # Let the model process all tool results
            result = kayo.invoke(message)
            message.append(result)

        return result.content

    except ModelRateLimitError as RLE:
        return f"Error: {str(RLE)} wait some time for reset this limit."

    except Exception as E:
        return f"Error: '{str(E)}'"