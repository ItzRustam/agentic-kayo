import subprocess
import os

from langchain_core.tools import tool


@tool
def run_command(command: str) -> str:
    """Execute a command inside the Debian Docker container. Use for coding, files, installing dependencies, running programs, debugging, and system utilities."""

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/",
        )

        output = []

        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")

        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")

        output.append(f"EXIT CODE: {result.returncode}")

        response = "\n".join(output)

        # Prevent massive tool outputs from consuming context tokens
        max_chars = 12000

        if len(response) > max_chars:
            response = response[:max_chars] + "\n\n[Output truncated]"

        return response

    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 60 seconds."

    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"