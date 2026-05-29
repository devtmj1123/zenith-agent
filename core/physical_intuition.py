"""Physical Intuition — Structural validation of actions before execution.

Not hints. Not suggestions. Hard constraints that validate whether an action
is physically possible, safe, and sensible before the model wastes tokens on it.

Three levels:
1. DENY — Action is impossible or dangerous. Block immediately.
2. WARN — Action may fail. Inject constraint into context.
3. ALLOW — Action is valid. Proceed.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ValidationLevel(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    DENY = "deny"


@dataclass
class ValidationVerdict:
    level: ValidationLevel
    reason: str
    hint: str = ""  # Injected into context if WARN


class PhysicalIntuition:
    """Validates actions against physical constraints before execution."""

    # Paths that should never be deleted (normalized)
    PROTECTED_PATHS = {
        os.sep,  # Root: "/" on Unix, "\" on Windows
        "/bin", "/usr", "/etc", "/system",
        "c:\\windows", "c:\\program files", "c:\\users",
    }

    # Dangerous commands
    DANGEROUS_COMMANDS = [
        "rm -rf /", "rm -rf /*", "rmdir /s /q C:\\",
        "format", "del /f /s /q C:\\",
        "shutdown", "reboot", "taskkill /f /im",
    ]

    def validate_action(self, func_name: str, params: dict,
                        context: str = "") -> ValidationVerdict:
        """Validate an action against physical constraints.

        Returns ALLOW/WARN/DENY with reason and optional hint.
        """
        # File operations
        if func_name in ("read_file", "write_file", "edit_file", "delete_file"):
            return self._validate_file_action(func_name, params)

        # Shell commands
        if func_name in ("run_command", "python_exec", "git"):
            return self._validate_shell_action(func_name, params)

        # URL operations
        if func_name in ("navigate", "fetch", "scrape"):
            return self._validate_url_action(func_name, params)

        # App operations
        if func_name in ("open_app", "close_app"):
            return self._validate_app_action(func_name, params)

        return ValidationVerdict(ValidationLevel.ALLOW, "OK")

    def _validate_file_action(self, func_name: str,
                               params: dict) -> ValidationVerdict:
        """Validate file operations."""
        path = params.get("path", "")
        if not path:
            return ValidationVerdict(
                ValidationLevel.DENY, "No path specified"
            )

        # Normalize path
        norm_path = os.path.normpath(path).lower() if path else ""

        # Protect critical paths
        if func_name == "delete_file":
            for protected in self.PROTECTED_PATHS:
                protected_norm = os.path.normpath(protected).lower()
                if norm_path == protected_norm or norm_path.startswith(protected_norm + os.sep):
                    return ValidationVerdict(
                        ValidationLevel.DENY,
                        f"Cannot delete protected path: {path}"
                    )

        # Check if file exists for read/edit
        if func_name in ("read_file", "edit_file"):
            if not Path(path).exists():
                return ValidationVerdict(
                    ValidationLevel.WARN,
                    f"File may not exist: {path}",
                    hint=f"Note: {path} may not exist. Check before proceeding."
                )

        # Check parent directory for write
        if func_name == "write_file":
            parent = Path(path).parent
            if not parent.exists():
                return ValidationVerdict(
                    ValidationLevel.WARN,
                    f"Parent directory may not exist: {parent}",
                    hint=f"Note: Directory {parent} may need to be created first."
                )

        return ValidationVerdict(ValidationLevel.ALLOW, "OK")

    def _validate_shell_action(self, func_name: str,
                                params: dict) -> ValidationVerdict:
        """Validate shell commands."""
        command = params.get("command", "") or params.get("code", "") or params.get("subcommand", "")
        if not command:
            return ValidationVerdict(
                ValidationLevel.DENY, "No command specified"
            )

        cmd_lower = command.lower().strip()

        # Check for dangerous commands
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return ValidationVerdict(
                    ValidationLevel.DENY,
                    f"Dangerous command blocked: {dangerous}"
                )

        # Warn about sudo/admin
        if "sudo" in cmd_lower or "runas" in cmd_lower:
            return ValidationVerdict(
                ValidationLevel.WARN,
                "Command requires elevated privileges",
                hint="This command needs admin/root. It may fail without proper permissions."
            )

        return ValidationVerdict(ValidationLevel.ALLOW, "OK")

    def _validate_url_action(self, func_name: str,
                              params: dict) -> ValidationVerdict:
        """Validate URL operations."""
        url = params.get("url", "")
        if not url:
            return ValidationVerdict(
                ValidationLevel.DENY, "No URL specified"
            )

        # Basic URL format check
        if not re.match(r'https?://', url):
            return ValidationVerdict(
                ValidationLevel.WARN,
                f"URL may be malformed: {url}",
                hint=f"Note: {url} doesn't start with http:// or https://"
            )

        return ValidationVerdict(ValidationLevel.ALLOW, "OK")

    def _validate_app_action(self, func_name: str,
                              params: dict) -> ValidationVerdict:
        """Validate app operations."""
        app = params.get("app", "")
        if not app:
            return ValidationVerdict(
                ValidationLevel.DENY, "No app name specified"
            )

        return ValidationVerdict(ValidationLevel.ALLOW, "OK")

    def get_context_constraints(self, goal: str) -> str:
        """Return physical constraints relevant to the goal.

        These are injected into the system prompt to guide the model.
        """
        constraints = []
        goal_lower = goal.lower()

        # File operations
        if any(w in goal_lower for w in ["file", "read", "write", "save", "create"]):
            constraints.append("Files must exist before reading. Directories must exist before writing.")

        # Network operations
        if any(w in goal_lower for w in ["search", "fetch", "download", "api", "url"]):
            constraints.append("Network requests take time. Don't retry immediately on failure.")

        # App operations
        if any(w in goal_lower for w in ["open", "launch", "start", "app"]):
            constraints.append("Applications need time to start. Wait before interacting.")

        # Shell operations
        if any(w in goal_lower for w in ["run", "execute", "command", "shell"]):
            constraints.append("Commands may require specific environment or permissions.")

        if not constraints:
            return ""

        return "Physical constraints: " + " ".join(constraints)
