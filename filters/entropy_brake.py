from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from core.types import RegulatorDecision, RegulatorVerdict


# Action tokens that ARE destructive by nature (matched against ACT:NAME)
DESTRUCTIVE_ACTIONS = {
    "ACT:DELETE_FILE", "ACT:DELETE_DYNAMIC_TOOL",
}

# Patterns to check ONLY in command strings (run_command, shell, exec)
COMMAND_IRREVERSIBLE = [
    "rm -rf", "rmdir", "del /f", "format ",
    "mkfs", "fdisk", "diskpart",
]

# Safe actions that should NEVER be blocked (whitelist)
SAFE_ACTIONS = {
    "ACT:RECALL", "ACT:STORE_MEMORY", "ACT:GET_TIME", "ACT:GET_WEATHER",
    "ACT:READ_FILE", "ACT:LIST_DIR", "ACT:GLOB_SEARCH", "ACT:GREP_SEARCH",
    "ACT:WEB_SEARCH", "ACT:FETCH", "ACT:SCRAPE", "ACT:BROWSE_OPEN",
    "ACT:BROWSE_SNAPSHOT", "ACT:BROWSE_CLICK", "ACT:BROWSE_FILL",
    "ACT:BROWSE_GET", "ACT:BROWSE_SCREENSHOT", "ACT:BROWSE_SKILLS",
    "ACT:BROWSE_EVAL", "ACT:BROWSE_WAIT", "ACT:PARSE_DOCUMENT",
    "ACT:CHECK_BACKGROUND", "ACT:CALENDAR", "ACT:SPREADSHEET",
}


@dataclass
class EntropyBrakeResult:
    allowed: bool
    requires_confirmation: bool
    reason: str


class EntropyBrake:
    def check(self, action_token: str, params: dict,
              context: str = "") -> EntropyBrakeResult:
        # Safe actions are always allowed
        if action_token in SAFE_ACTIONS:
            return EntropyBrakeResult(allowed=True, requires_confirmation=False, reason="OK")

        # Destructive action tokens need confirmation
        if action_token in DESTRUCTIVE_ACTIONS:
            return EntropyBrakeResult(
                allowed=False,
                requires_confirmation=True,
                reason=f"Destructive action: {action_token}. Human confirmation required."
            )

        # For run_command: check the actual command string
        if action_token in ("ACT:RUN_COMMAND", "ACT:COMMAND"):
            cmd = str(params.get("command", "")).lower()
            for pattern in COMMAND_IRREVERSIBLE:
                if pattern in cmd:
                    return EntropyBrakeResult(
                        allowed=False,
                        requires_confirmation=True,
                        reason=f"Irreversible command detected: '{pattern.strip()}' in command. "
                               f"Human confirmation required."
                    )

        # For edit_file/write_file: check if targeting critical paths
        if action_token in ("ACT:WRITE_FILE", "ACT:EDIT_FILE"):
            path = str(params.get("path", "")).lower()
            critical = ["/etc/", "/boot/", "/sys/", "/proc/", "c:\\windows\\", "c:\\program files"]
            for c in critical:
                if c in path:
                    return EntropyBrakeResult(
                        allowed=False,
                        requires_confirmation=True,
                        reason=f"Critical path: {path}. Human confirmation required."
                    )

        return EntropyBrakeResult(allowed=True, requires_confirmation=False, reason="OK")

    def verdict(self, action_token: str, params: dict) -> RegulatorVerdict:
        result = self.check(action_token, params)
        if result.requires_confirmation:
            return RegulatorVerdict(
                decision=RegulatorDecision.CONFIRM,
                reason=result.reason
            )
        return RegulatorVerdict(decision=RegulatorDecision.ALLOW, reason="Safe action")
