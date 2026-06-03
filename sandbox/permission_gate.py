"""Three-tier permission decision engine.

ALLOW   → execute immediately (safe, reversible actions)
CONFIRM → write to shadow, wait for user (risky or irreversible)
BLOCK   → hard refuse, log, never execute

Zero LLM calls — pure deterministic logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class Decision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


@dataclass
class GateResult:
    decision: Decision
    reason: str
    rule_id: str = ""
    shadow_required: bool = False


class PermissionGate:
    """Evaluates every agent action before execution. Zero LLM calls."""

    def __init__(self, settings=None):
        self._rules = self._load()
        self._autopilot = False
        if settings:
            self._autopilot = getattr(settings, "autopilot", False)

    def check(self, tool_name: str, params: dict,
              context_source: str = "agent") -> GateResult:
        """Main entry point. Called before EVERY tool execution."""
        # 1. Hard blocks — no exceptions
        block = self._check_hard_blocks(tool_name, params)
        if block:
            return block

        # 2. Always-allowed tools (safe reads)
        if tool_name in self._rules.get("always_allow", []):
            return GateResult(Decision.ALLOW, "Always allowed", "always_allow")

        # 3. External content → escalate risk
        if context_source in ("external_web", "external_file"):
            return GateResult(
                Decision.CONFIRM,
                "External content triggered action — requires approval",
                "external_source_escalation",
                shadow_required=True,
            )

        # 4. High-risk tool check
        if tool_name in self._rules.get("high_risk_tools", []):
            if self._autopilot:
                return GateResult(
                    Decision.ALLOW, "Autopilot: high-risk allowed", "autopilot",
                    shadow_required=True,
                )
            return GateResult(
                Decision.CONFIRM,
                f"High-risk tool '{tool_name}' requires approval",
                "high_risk_tool",
                shadow_required=True,
            )

        # 5. Path-based rules for file operations
        if tool_name in ("file_ops", "shell", "run_command"):
            path_result = self._check_path_rules(params)
            if path_result:
                return path_result

        # 6. Network rules
        if tool_name in ("web_scraper", "web_search", "browser"):
            net_result = self._check_network_rules(params)
            if net_result:
                return net_result

        # 7. Default: allow with shadow if writing
        is_write = self._is_write_action(tool_name, params)
        return GateResult(
            Decision.ALLOW, "Default allow", "default",
            shadow_required=is_write,
        )

    # ── Rule checkers ──────────────────────────────────────────────────────

    def _check_hard_blocks(self, tool_name: str, params: dict) -> Optional[GateResult]:
        cmd = (str(params.get("command", "")) +
               str(params.get("code", "")) +
               str(params.get("path", ""))).lower()

        for pattern in self._rules.get("hard_block_patterns", []):
            if re.search(pattern, cmd, re.IGNORECASE):
                return GateResult(
                    Decision.BLOCK,
                    f"Hard blocked: '{pattern}'",
                    "hard_block",
                )

        # Block modification of Zenith core
        protected = [".zenith/core", "core/agent_loop", "core/flow_regulator",
                     "sandbox/permission_gate"]
        for p in protected:
            if p in cmd:
                return GateResult(
                    Decision.BLOCK, "Cannot modify Zenith core", "immutable_core",
                )
        return None

    def _check_path_rules(self, params: dict) -> Optional[GateResult]:
        path = str(params.get("path", "")).lower().replace("\\", "/")

        system_paths = [
            "c:/windows", "c:/program files",
            "/etc", "/bin", "/usr/bin", "/sys", "/proc",
        ]
        for sp in system_paths:
            if path.startswith(sp):
                return GateResult(
                    Decision.BLOCK, f"System path protected: {path}", "system_path_block",
                )

        sensitive = ["appdata/roaming", ".ssh", ".aws", ".gnupg", "passwords"]
        for s in sensitive:
            if s in path:
                return GateResult(
                    Decision.CONFIRM, f"Sensitive directory: {path}", "sensitive_path",
                    shadow_required=True,
                )
        return None

    def _check_network_rules(self, params: dict) -> Optional[GateResult]:
        url = str(params.get("url", "") or params.get("query", "")).lower()
        for pattern in self._rules.get("blocked_domains", []):
            if pattern in url:
                return GateResult(
                    Decision.BLOCK, f"Blocked domain: {pattern}", "domain_block"
                )
        return None

    def _is_write_action(self, tool_name: str, params: dict) -> bool:
        write_tools = {"file_ops", "shell", "code_exec", "browser", "run_command"}
        if tool_name not in write_tools:
            return False
        action = str(params.get("action", "")).lower()
        write_actions = {"write", "delete", "edit", "append", "execute", "run"}
        return action in write_actions or tool_name in ("shell", "code_exec", "run_command")

    def _load(self) -> dict:
        path = Path("config/permissions.yaml")
        if not path.exists():
            return self._defaults()
        try:
            with open(path) as f:
                return yaml.safe_load(f) or self._defaults()
        except Exception:
            return self._defaults()

    def _defaults(self) -> dict:
        return {
            "always_allow": [
                "web_search", "calculator", "datetime_tool",
                "memory_tool", "system_info", "vision",
            ],
            "high_risk_tools": ["shell", "code_exec", "browser", "app_control"],
            "hard_block_patterns": [
                r"rm\s+-rf\s+/", r"format\s+c:", r"mkfs",
                r"dd\s+if=", r":\(\)\{:\|:&\};:",
                r"DROP\s+DATABASE", r"shutdown\s+/[sr]",
            ],
            "blocked_domains": ["malware", "phishing", "ransomware"],
        }
