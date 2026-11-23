"""Central configuration loader and validator for Agentic Kayo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env once centrally
_ENV_LOADED = False


def load_environment(dotenv_path: str | Path | None = None) -> None:
    """Load environment variables from .env file."""
    global _ENV_LOADED
    if not _ENV_LOADED:
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=True)
        else:
            load_dotenv()
        _ENV_LOADED = True


# Ensure .env is loaded when config module is imported
load_environment()


@dataclass(frozen=True)
class AppConfig:
    google_api_key: str
    openrouter_api_key: str
    kayo_model: str
    codegen_model: str
    vosk_model_path: str
    max_agent_steps: int
    mail_password: str
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    app_timezone: str
    kayo_workspace: str
    python_runner_url: str

    @property
    def workspace_path(self) -> Path:
        """Resolve workspace path and ensure directory exists."""
        resolved = Path(self.kayo_workspace).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def validate_google_credentials(self) -> None:
        """Check if Google API key is provided."""
        if not self.google_api_key.strip():
            raise ValueError(
                "GOOGLE_API_KEY is missing. Please set it in your .env file or environment."
            )

    def validate_openrouter_credentials(self) -> None:
        """Check if OpenRouter API key is provided."""
        if not self.openrouter_api_key.strip():
            raise ValueError(
                "OPENROUTER_API_KEY is missing. Please set it in your .env file or environment."
            )

    def validate(self) -> list[str]:
        """Perform validation and return list of warnings/issues (non-fatal)."""
        issues: list[str] = []
        if self.max_agent_steps < 1:
            issues.append(f"MAX_AGENT_STEPS should be at least 1, got {self.max_agent_steps}")
        if self.smtp_port < 1 or self.smtp_port > 65535:
            issues.append(f"Invalid SMTP_PORT: {self.smtp_port}")
        return issues


def get_config() -> AppConfig:
    """Read configuration from environment variables with sensible defaults."""
    # Ensure environment is loaded
    load_environment()

    # Determine default workspace: /workspace if writable/exists, else ./workspace
    raw_workspace = os.getenv("KAYO_WORKSPACE")
    if not raw_workspace:
        if os.path.exists("/workspace") and os.access("/workspace", os.W_OK):
            raw_workspace = "/workspace"
        else:
            raw_workspace = "./workspace"

    smtp_port_raw = os.getenv("SMTP_PORT", "587")
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    max_steps_raw = os.getenv("MAX_AGENT_STEPS", "8")
    try:
        max_agent_steps = int(max_steps_raw)
    except ValueError:
        max_agent_steps = 8

    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes", "on")

    return AppConfig(
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        kayo_model=os.getenv("KAYO_MODEL", "gemini-3.5-flash-lite").strip(),
        codegen_model=os.getenv("CODEGEN_MODEL", "baidu/ernie-5.5-flash-preview:free").strip(),
        vosk_model_path=os.getenv("VOSK_MODEL_PATH", "models/en-small").strip(),
        max_agent_steps=max_agent_steps,
        mail_password=os.getenv("MAIL_PASSWORD", "").strip(),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=smtp_port,
        smtp_use_tls=smtp_use_tls,
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip(),
        kayo_workspace=raw_workspace,
        python_runner_url=os.getenv("PYTHON_RUNNER_URL", "http://python-runner:8765").strip(),
    )
