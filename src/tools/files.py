"""Workspace file operations with strict boundary and security checks."""

from __future__ import annotations

import difflib
import logging
import os
from pathlib import Path
from typing import Any

from src.config import get_config

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB
MAX_READ_CHARS = 50_000

FORBIDDEN_NAMES = {
    ".env",
    ".git",
    ".venv",
    "__pycache__",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
}


def _resolve_safe_path(user_path: str, workspace_root: Path | None = None) -> Path:
    """
    Resolve user-supplied path strictly against workspace root.
    Rejects directory traversal, symlink escapes, and restricted paths.
    """
    if not user_path or not str(user_path).strip():
        raise ValueError("File path cannot be empty.")

    clean_path = str(user_path).strip()

    # Reject null bytes
    if "\0" in clean_path:
        raise ValueError("Path contains invalid characters.")

    ws = workspace_root or get_config().workspace_path
    ws_resolved = ws.resolve()

    # If path is given as absolute, check if it starts with the workspace path
    raw_path = Path(clean_path)
    if raw_path.is_absolute():
        try:
            rel = raw_path.resolve().relative_to(ws_resolved)
            target = ws_resolved / rel
        except ValueError:
            raise ValueError(f"Access denied: Path '{clean_path}' is outside the workspace.")
    else:
        target = (ws_resolved / raw_path).resolve()

    # Ensure target is strictly inside workspace root
    try:
        target.relative_to(ws_resolved)
    except ValueError:
        raise ValueError(f"Access denied: Path '{clean_path}' traverses outside workspace.")

    # Check for forbidden names in path parts
    for part in target.relative_to(ws_resolved).parts:
        if part in FORBIDDEN_NAMES or part.startswith(".env"):
            raise ValueError(f"Access denied: Access to '{part}' is forbidden.")

    # Check symlink escapes if target exists
    if target.is_symlink():
        symlink_target = target.resolve()
        try:
            symlink_target.relative_to(ws_resolved)
        except ValueError:
            raise ValueError("Access denied: Symlink resolves outside the workspace.")

    return target


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file appears to be binary by reading a small chunk."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except Exception:
        return False


def create_file(
    path: str,
    content: str,
    overwrite: bool = False,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """
    Create a UTF-8 text file in Kayo's workspace.
    Refuses to overwrite an existing file unless overwrite=True.
    """
    try:
        target = _resolve_safe_path(path, workspace_root)
        if target.exists() and not overwrite:
            return {
                "ok": False,
                "tool": "create_file",
                "error": f"File already exists: '{path}'. Set overwrite=True to overwrite.",
            }

        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_FILE_SIZE_BYTES:
            return {
                "ok": False,
                "tool": "create_file",
                "error": f"Content exceeds maximum file size limit of {MAX_FILE_SIZE_BYTES} bytes.",
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "ok": True,
            "tool": "create_file",
            "result": {
                "path": str(target.relative_to((workspace_root or get_config().workspace_path).resolve())),
                "bytes_written": len(content_bytes),
                "overwritten": target.exists() and overwrite,
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "create_file", "error": str(exc)}


def read_file(path: str, workspace_root: Path | None = None) -> dict[str, Any]:
    """
    Read a UTF-8 text file from the workspace.
    Truncates content with a clear notice if it exceeds limits.
    """
    try:
        target = _resolve_safe_path(path, workspace_root)
        if not target.exists():
            return {"ok": False, "tool": "read_file", "error": f"File not found: '{path}'."}

        if target.is_dir():
            return {"ok": False, "tool": "read_file", "error": f"Path '{path}' is a directory, not a file."}

        if _is_binary_file(target):
            return {"ok": False, "tool": "read_file", "error": f"File '{path}' is binary and cannot be read as text."}

        file_size = target.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return {
                "ok": False,
                "tool": "read_file",
                "error": f"File size ({file_size} bytes) exceeds {MAX_FILE_SIZE_BYTES} bytes limit.",
            }

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_READ_CHARS + 1)

        truncated = len(content) > MAX_READ_CHARS
        if truncated:
            content = content[:MAX_READ_CHARS]

        rel_path = str(target.relative_to((workspace_root or get_config().workspace_path).resolve()))
        return {
            "ok": True,
            "tool": "read_file",
            "result": {
                "path": rel_path,
                "content": content,
                "truncated": truncated,
                "total_chars": len(content),
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "read_file", "error": str(exc)}


def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """
    Replace an exact text fragment in a workspace file.
    Requires an unambiguous single match. Returns diff preview.
    """
    try:
        target = _resolve_safe_path(path, workspace_root)
        if not target.exists() or not target.is_file():
            return {"ok": False, "tool": "edit_file", "error": f"File not found: '{path}'."}

        if _is_binary_file(target):
            return {"ok": False, "tool": "edit_file", "error": f"Cannot edit binary file '{path}'."}

        with open(target, "r", encoding="utf-8") as f:
            original = f.read()

        count = original.count(old_text)
        if count == 0:
            return {
                "ok": False,
                "tool": "edit_file",
                "error": "The specified old_text was not found in the file.",
            }
        elif count > 1:
            return {
                "ok": False,
                "tool": "edit_file",
                "error": f"Ambiguous match: old_text appears {count} times in '{path}'. Must match exactly once.",
            }

        updated = original.replace(old_text, new_text, 1)

        # Generate diff preview
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                updated.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )

        with open(target, "w", encoding="utf-8") as f:
            f.write(updated)

        rel_path = str(target.relative_to((workspace_root or get_config().workspace_path).resolve()))
        return {
            "ok": True,
            "tool": "edit_file",
            "result": {
                "path": rel_path,
                "diff": diff,
                "message": f"Successfully edited '{rel_path}'.",
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "edit_file", "error": str(exc)}


def list_files(
    path: str = ".",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """
    List files and directories under workspace path.
    Excludes hidden files and internal directories by default.
    """
    try:
        target = _resolve_safe_path(path, workspace_root)
        if not target.exists() or not target.is_dir():
            return {"ok": False, "tool": "list_files", "error": f"Directory not found: '{path}'."}

        ws_resolved = (workspace_root or get_config().workspace_path).resolve()
        entries = []
        for entry in sorted(target.iterdir()):
            if entry.name.startswith(".") or entry.name in FORBIDDEN_NAMES:
                continue
            is_dir = entry.is_dir()
            entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(ws_resolved)),
                "is_dir": is_dir,
                "size_bytes": 0 if is_dir else entry.stat().st_size,
            })

        return {
            "ok": True,
            "tool": "list_files",
            "result": {
                "directory": str(target.relative_to(ws_resolved)),
                "items": entries,
                "count": len(entries),
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "list_files", "error": str(exc)}


def search_files(
    query: str,
    path: str = ".",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """
    Search text files under the workspace for query string.
    Returns matching relative paths and line numbers.
    """
    cleaned_query = str(query).strip()
    if not cleaned_query:
        return {"ok": False, "tool": "search_files", "error": "Search query cannot be empty."}

    try:
        target = _resolve_safe_path(path, workspace_root)
        if not target.exists() or not target.is_dir():
            return {"ok": False, "tool": "search_files", "error": f"Directory not found: '{path}'."}

        ws_resolved = (workspace_root or get_config().workspace_path).resolve()
        matches = []

        for root, dirs, files in os.walk(target):
            # Prune forbidden and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in FORBIDDEN_NAMES]

            for file_name in files:
                if file_name.startswith(".") or file_name in FORBIDDEN_NAMES:
                    continue

                file_path = Path(root) / file_name
                if _is_binary_file(file_path):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            if cleaned_query in line:
                                matches.append({
                                    "path": str(file_path.relative_to(ws_resolved)),
                                    "line": lineno,
                                    "text": line.strip()[:200],
                                })
                                if len(matches) >= 100:
                                    break
                except Exception:
                    continue

            if len(matches) >= 100:
                break

        return {
            "ok": True,
            "tool": "search_files",
            "result": {
                "query": cleaned_query,
                "matches": matches,
                "total_matches": len(matches),
                "capped": len(matches) >= 100,
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "search_files", "error": str(exc)}


def delete_file(
    path: str,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """
    Delete one regular file inside the workspace only.
    Refuses to delete directories. Requires confirmation.
    """
    try:
        target = _resolve_safe_path(path, workspace_root)
        if not target.exists():
            return {"ok": False, "tool": "delete_file", "error": f"File not found: '{path}'."}

        if target.is_dir():
            return {
                "ok": False,
                "tool": "delete_file",
                "error": f"Path '{path}' is a directory. Recursive directory deletion is prohibited.",
            }

        rel_path = str(target.relative_to((workspace_root or get_config().workspace_path).resolve()))
        target.unlink()

        return {
            "ok": True,
            "tool": "delete_file",
            "result": {
                "path": rel_path,
                "message": f"Successfully deleted file '{rel_path}'.",
            },
        }
    except Exception as exc:
        return {"ok": False, "tool": "delete_file", "error": str(exc)}
