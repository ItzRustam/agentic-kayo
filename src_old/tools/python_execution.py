"""Client tools for executing Python code and files through the isolated runner."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from src_old.config import get_config
from src_old.runner.server import execute_python_cmd, _resolve_runner_path
import sys

logger = logging.getLogger(__name__)


def _call_runner_api(endpoint: str, payload: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    """Attempt to send execution request to the isolated python-runner HTTP service."""
    base_url = get_config().python_runner_url.rstrip("/")
    url = f"{base_url}/{endpoint.lstrip('/')}"

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except (urllib.error.URLError, ConnectionRefusedError, OSError) as exc:
        logger.debug("Python runner service unavailable at %s: %s. Using local workspace executor fallback.", url, exc)
        return None


def run_python_code(code: str, timeout: int = 10) -> dict[str, Any]:
    """
    Execute a Python snippet through the isolated Python runner.
    Returns stdout, stderr, exit code, elapsed time, and timeout status.
    Requires explicit user confirmation before execution.
    """
    clean_code = str(code).strip()
    if not clean_code:
        return {
            "ok": False,
            "tool": "run_python_code",
            "error": "No Python code provided for execution.",
        }

    # Attempt to send to python-runner container service
    runner_response = _call_runner_api("run_code", {"code": clean_code, "timeout": timeout}, timeout=timeout)
    if runner_response is not None:
        if runner_response.get("ok"):
            return {
                "ok": True,
                "tool": "run_python_code",
                "result": runner_response["result"],
            }
        return {
            "ok": False,
            "tool": "run_python_code",
            "error": runner_response.get("error", "Runner returned an error."),
        }

    # Fallback: execute safely in local workspace using sys.executable without shell
    ws = get_config().workspace_path
    import tempfile
    from pathlib import Path

    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=str(ws),
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(clean_code)
            tmp_file = Path(f.name)

        res = execute_python_cmd([sys.executable, "-u", str(tmp_file)], cwd=ws, timeout=timeout)
        return {
            "ok": True,
            "tool": "run_python_code",
            "result": res,
        }
    except Exception as exc:
        return {
            "ok": False,
            "tool": "run_python_code",
            "error": f"Local execution failed: {exc}",
        }
    finally:
        if tmp_file and tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass


def run_python_file(
    path: str,
    args: list[str] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """
    Execute an existing .py file inside the workspace through the isolated Python runner.
    Arguments are passed as an array, never as a shell string.
    Requires explicit user confirmation before execution.
    """
    clean_path = str(path).strip()
    if not clean_path:
        return {
            "ok": False,
            "tool": "run_python_file",
            "error": "File path cannot be empty.",
        }

    args_list = args or []
    if not isinstance(args_list, list):
        return {
            "ok": False,
            "tool": "run_python_file",
            "error": "args must be a list of strings.",
        }

    str_args = [str(a) for a in args_list]

    # Attempt to send to python-runner service
    runner_response = _call_runner_api(
        "run_file",
        {"path": clean_path, "args": str_args, "timeout": timeout},
        timeout=timeout,
    )
    if runner_response is not None:
        if runner_response.get("ok"):
            return {
                "ok": True,
                "tool": "run_python_file",
                "result": runner_response["result"],
            }
        return {
            "ok": False,
            "tool": "run_python_file",
            "error": runner_response.get("error", "Runner returned an error."),
        }

    # Fallback: execute safely in local workspace using sys.executable without shell
    ws = get_config().workspace_path
    try:
        target = _resolve_runner_path(clean_path, ws)
        res = execute_python_cmd([sys.executable, "-u", str(target), *str_args], cwd=ws, timeout=timeout)
        return {
            "ok": True,
            "tool": "run_python_file",
            "result": res,
        }
    except Exception as exc:
        return {
            "ok": False,
            "tool": "run_python_file",
            "error": str(exc),
        }
