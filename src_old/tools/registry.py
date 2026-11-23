"""Unified Tool Registry and Dispatcher for Agentic Kayo."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from src_old.tools.files import (
    create_file,
    delete_file,
    edit_file,
    list_files,
    read_file,
    search_files,
)
from src_old.tools.open_website import open_website
from src_old.tools.python_execution import run_python_code, run_python_file
from src_old.tools.search_wikipedia import search_wikipedia
from src_old.tools.send_mail import prepare_mail_preview, send_mail
from src_old.tools.utilities import calculate, get_current_datetime
from src_old.tools.web_search import web_search

logger = logging.getLogger(__name__)

# Tools requiring explicit user confirmation before side effects occur
CONFIRMATION_REQUIRED_TOOLS = {
    "send_mail",
    "delete_file",
    "run_python_code",
    "run_python_file",
}


# =====================================================================
# Pydantic Schemas for All 14 Tools
# =====================================================================

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query string to look up on the web.")
    max_results: int = Field(default=5, description="Maximum number of search results to return (1-10).")


class SearchWikipediaInput(BaseModel):
    query: str = Field(description="The topic or article title to search on Wikipedia.")


class OpenWebsiteInput(BaseModel):
    url: str = Field(description="The absolute HTTP or HTTPS URL to open as a clickable link.")


class CreateFileInput(BaseModel):
    path: str = Field(description="Relative path of the text file inside the workspace to create.")
    content: str = Field(description="The text content to write into the file.")
    overwrite: bool = Field(default=False, description="Set to True only if explicitly intending to overwrite an existing file.")


class ReadFileInput(BaseModel):
    path: str = Field(description="Relative path of the workspace text file to read.")


class EditFileInput(BaseModel):
    path: str = Field(description="Relative path of the workspace text file to edit.")
    old_text: str = Field(description="The exact text fragment to be replaced. Must match exactly once.")
    new_text: str = Field(description="The new replacement text.")


class ListFilesInput(BaseModel):
    path: str = Field(default=".", description="Relative directory path under the workspace to list.")


class SearchFilesInput(BaseModel):
    query: str = Field(description="Text string to search for across text files in the workspace.")
    path: str = Field(default=".", description="Starting directory path under the workspace.")


class DeleteFileInput(BaseModel):
    path: str = Field(description="Relative path of the single file inside the workspace to delete. Requires confirmation.")


class RunPythonCodeInput(BaseModel):
    code: str = Field(description="Python 3.13 code snippet to execute inside the isolated runner container. Requires confirmation.")


class RunPythonFileInput(BaseModel):
    path: str = Field(description="Relative path to an existing .py script inside the workspace. Requires confirmation.")
    args: list[str] | None = Field(default=None, description="Optional command-line arguments to pass to the script.")


class CalculateInput(BaseModel):
    expression: str = Field(description="Arithmetic expression to evaluate (e.g., '(12 + 5) * 3 / 2').")


class GetCurrentDatetimeInput(BaseModel):
    pass


class SendMailInput(BaseModel):
    to: str = Field(description="Recipient email address.")
    subject: str = Field(description="Subject line of the email.")
    body: str = Field(description="Plain text message body. Requires confirmation before sending.")


# =====================================================================
# Tool Definition Spec
# =====================================================================

@dataclass
class ToolSpec:
    name: str
    description: str
    func: Callable[..., Any]
    schema: type[BaseModel]
    requires_confirmation: bool = False


# Activity log for UI / dashboard
_TOOL_ACTIVITY_LOG: list[dict[str, Any]] = []


def get_tool_activity_log(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent tool execution history."""
    return list(_TOOL_ACTIVITY_LOG[-limit:])


def clear_tool_activity_log() -> None:
    _TOOL_ACTIVITY_LOG.clear()


class ToolRegistry:
    """Central registry and dispatcher for all Agentic Kayo tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._register_all_tools()

    def register(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        schema: type[BaseModel],
        requires_confirmation: bool = False,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            func=func,
            schema=schema,
            requires_confirmation=requires_confirmation,
        )

    def get_tool_spec(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tool_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get_langchain_tools(self) -> list[BaseTool]:
        """Convert all registered tools to LangChain StructuredTools."""
        lc_tools: list[BaseTool] = []
        for spec in self._tools.values():
            tool = StructuredTool.from_function(
                func=spec.func,
                name=spec.name,
                description=spec.description,
                args_schema=spec.schema,
            )
            lc_tools.append(tool)
        return lc_tools

    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        bypass_confirmation: bool = False,
    ) -> dict[str, Any]:
        """
        Validate and execute a tool by name.
        Enforces confirmation gating for sensitive tools unless bypass_confirmation=True.
        """
        spec = self._tools.get(name)
        if not spec:
            err_msg = f"Unknown tool '{name}'. Valid tools: {', '.join(sorted(self._tools.keys()))}"
            logger.warning(err_msg)
            return {"ok": False, "tool": name, "error": err_msg}

        # Validate arguments using Pydantic schema
        try:
            validated_args = spec.schema(**arguments).model_dump(exclude_unset=False)
        except Exception as val_err:
            err_msg = f"Invalid arguments for tool '{name}': {val_err}"
            logger.warning(err_msg)
            return {"ok": False, "tool": name, "error": err_msg}

        # Check confirmation gate
        if spec.requires_confirmation and not bypass_confirmation:
            # Special preview for email
            preview = None
            if name == "send_mail":
                preview_res = prepare_mail_preview(
                    to=validated_args.get("to", ""),
                    subject=validated_args.get("subject", ""),
                    body=validated_args.get("body", ""),
                )
                if not preview_res["ok"]:
                    return preview_res
                preview = preview_res["preview"]

            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": name,
                "duration_seconds": 0.0,
                "status": "requires_confirmation",
            }
            _TOOL_ACTIVITY_LOG.append(record)

            return {
                "ok": False,
                "tool": name,
                "requires_confirmation": True,
                "arguments": validated_args,
                "preview": preview,
                "message": f"Action '{name}' requires explicit user confirmation before proceeding.",
            }

        # Execute tool
        start_time = time.time()
        try:
            # Clean empty args for zero-arg tools
            if spec.schema == GetCurrentDatetimeInput:
                result = spec.func()
            else:
                result = spec.func(**validated_args)

            duration = round(time.time() - start_time, 3)
            status = "success" if result.get("ok", False) else "error"

            _TOOL_ACTIVITY_LOG.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": name,
                "duration_seconds": duration,
                "status": status,
            })

            return result

        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            logger.exception("Error executing tool '%s': %s", name, exc)
            _TOOL_ACTIVITY_LOG.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": name,
                "duration_seconds": duration,
                "status": "exception",
            })
            return {"ok": False, "tool": name, "error": f"Tool execution error: {str(exc)}"}

    def _register_all_tools(self) -> None:
        """Register the 14 standard tools specified in Section 7."""

        # 1. web_search
        self.register(
            name="web_search",
            description="Search the web and return concise structured results containing title, URL, and snippet.",
            func=web_search,
            schema=WebSearchInput,
            requires_confirmation=False,
        )

        # 2. search_wikipedia
        self.register(
            name="search_wikipedia",
            description="Search Wikipedia and return ONLY a concise article summary, title, and canonical page URL. Never returns full article.",
            func=search_wikipedia,
            schema=SearchWikipediaInput,
            requires_confirmation=False,
        )

        # 3. open_website
        self.register(
            name="open_website",
            description="Validate an absolute HTTP/HTTPS URL and present it to the user as a clickable web link.",
            func=open_website,
            schema=OpenWebsiteInput,
            requires_confirmation=False,
        )

        # 4. create_file
        self.register(
            name="create_file",
            description="Create a text file in Kayo's workspace. Refuses to overwrite existing files unless overwrite=True.",
            func=create_file,
            schema=CreateFileInput,
            requires_confirmation=False,
        )

        # 5. read_file
        self.register(
            name="read_file",
            description="Read a UTF-8 text file from the workspace and return its content.",
            func=read_file,
            schema=ReadFileInput,
            requires_confirmation=False,
        )

        # 6. edit_file
        self.register(
            name="edit_file",
            description="Replace an exact text fragment in a workspace file. Requires an unambiguous single match.",
            func=edit_file,
            schema=EditFileInput,
            requires_confirmation=False,
        )

        # 7. list_files
        self.register(
            name="list_files",
            description="List files and directories under the workspace. Excludes hidden and cache files by default.",
            func=list_files,
            schema=ListFilesInput,
            requires_confirmation=False,
        )

        # 8. search_files
        self.register(
            name="search_files",
            description="Search text files under the workspace for matching lines and return relative paths with line numbers.",
            func=search_files,
            schema=SearchFilesInput,
            requires_confirmation=False,
        )

        # 9. delete_file
        self.register(
            name="delete_file",
            description="Delete one regular file inside the workspace only. Requires explicit user confirmation.",
            func=delete_file,
            schema=DeleteFileInput,
            requires_confirmation=True,
        )

        # 10. run_python_code
        self.register(
            name="run_python_code",
            description="Execute a Python 3.13 code snippet through the isolated Python runner. Requires explicit user confirmation.",
            func=run_python_code,
            schema=RunPythonCodeInput,
            requires_confirmation=True,
        )

        # 11. run_python_file
        self.register(
            name="run_python_file",
            description="Execute an existing .py file inside the workspace through the isolated runner. Requires explicit user confirmation.",
            func=run_python_file,
            schema=RunPythonFileInput,
            requires_confirmation=True,
        )

        # 12. calculate
        self.register(
            name="calculate",
            description="Evaluate basic arithmetic operations using a restricted safe AST evaluator without eval().",
            func=calculate,
            schema=CalculateInput,
            requires_confirmation=False,
        )

        # 13. get_current_datetime
        self.register(
            name="get_current_datetime",
            description="Return the current date and time in the configured APP_TIMEZONE.",
            func=get_current_datetime,
            schema=GetCurrentDatetimeInput,
            requires_confirmation=False,
        )

        # 14. send_mail
        self.register(
            name="send_mail",
            description="Send an email using SMTP credentials from .env and profile sender identity. Requires explicit user confirmation.",
            func=send_mail,
            schema=SendMailInput,
            requires_confirmation=True,
        )


# Global default registry instance
default_registry = ToolRegistry()
