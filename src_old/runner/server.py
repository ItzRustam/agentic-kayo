"""Isolated Python runner server running inside the python-runner container."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 50_000
DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 30


def get_workspace() -> Path:
    ws = os.getenv("RUNNER_WORKSPACE", "/workspace")
    path = Path(ws).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_runner_path(user_path: str, ws: Path) -> Path:
    """Resolve file path strictly inside RUNNER_WORKSPACE."""
    clean_path = str(user_path).strip()
    if not clean_path:
        raise ValueError("File path cannot be empty.")
    if "\0" in clean_path:
        raise ValueError("Invalid path characters.")

    target = (ws / clean_path).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        raise ValueError(f"Path '{user_path}' escapes workspace boundary.")

    if not target.suffix.lower() == ".py":
        raise ValueError("Only .py files may be executed.")

    if not target.exists() or not target.is_file():
        raise ValueError(f"Python script not found: '{user_path}'.")

    return target


def execute_python_cmd(
    cmd_args: list[str],
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Execute command with timeout and output limits using explicit argument array."""
    start_time = time.time()
    clamped_timeout = min(max(1, timeout), MAX_TIMEOUT)

    try:
        proc = subprocess.run(
            cmd_args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=clamped_timeout,
        )
        elapsed = round(time.time() - start_time, 3)

        stdout = proc.stdout
        stderr = proc.stderr
        stdout_truncated = len(stdout) > MAX_OUTPUT_CHARS
        stderr_truncated = len(stderr) > MAX_OUTPUT_CHARS

        if stdout_truncated:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n... [stdout truncated]"
        if stderr_truncated:
            stderr = stderr[:MAX_OUTPUT_CHARS] + "\n... [stderr truncated]"

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "timed_out": False,
            "elapsed_seconds": elapsed,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.time() - start_time, 3)
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return {
            "stdout": stdout,
            "stderr": (stderr + f"\nExecution timed out after {clamped_timeout} seconds.").strip(),
            "exit_code": -1,
            "timed_out": True,
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        elapsed = round(time.time() - start_time, 3)
        return {
            "stdout": "",
            "stderr": f"Execution failed: {exc}",
            "exit_code": -1,
            "timed_out": False,
            "elapsed_seconds": elapsed,
        }


class RunnerHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "python-runner"})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 1024 * 1024:  # 1 MB limit
            self._send_json(413, {"error": "Payload too large"})
            return

        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        ws = get_workspace()

        if self.path == "/run_code":
            code = data.get("code", "")
            timeout = int(data.get("timeout", DEFAULT_TIMEOUT))
            if not code or not code.strip():
                self._send_json(400, {"error": "No Python code provided"})
                return

            # Write code to a temporary file inside workspace
            tmp_file = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".py",
                    dir=str(ws),
                    delete=False,
                    encoding="utf-8",
                ) as f:
                    f.write(code)
                    tmp_file = Path(f.name)

                # Run Python file via sys.executable
                result = execute_python_cmd([sys.executable, "-u", str(tmp_file)], cwd=ws, timeout=timeout)
                self._send_json(200, {"ok": True, "result": result})
            finally:
                if tmp_file and tmp_file.exists():
                    try:
                        tmp_file.unlink()
                    except Exception:
                        pass

        elif self.path == "/run_file":
            rel_path = data.get("path", "")
            args = data.get("args") or []
            timeout = int(data.get("timeout", DEFAULT_TIMEOUT))

            if not isinstance(args, list):
                self._send_json(400, {"error": "Args must be an array of strings."})
                return

            # Ensure all args are strings
            str_args = [str(a) for a in args]

            try:
                target = _resolve_runner_path(rel_path, ws)
            except ValueError as err:
                self._send_json(400, {"ok": False, "error": str(err)})
                return

            result = execute_python_cmd([sys.executable, "-u", str(target), *str_args], cwd=ws, timeout=timeout)
            self._send_json(200, {"ok": True, "result": result})

        else:
            self._send_json(404, {"error": "Not Found"})


def run_server() -> None:
    host = os.getenv("RUNNER_HOST", "0.0.0.0")
    port = int(os.getenv("RUNNER_PORT", "8765"))
    server_address = (host, port)
    httpd = HTTPServer(server_address, RunnerHTTPRequestHandler)
    logger.info("Isolated Python Runner server listening on %s:%d", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Runner server shutting down.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
