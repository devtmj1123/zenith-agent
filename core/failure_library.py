from __future__ import annotations
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RecoveryStep:
    description: str
    action: str
    params_modifier: Optional[Dict] = None


@dataclass
class FailurePattern:
    pattern_id: str
    description: str
    recovery_chain: List[RecoveryStep]
    max_retries: int = 3


FAILURE_TREE: Dict[str, FailurePattern] = {
    "browser.element_not_found": FailurePattern(
        pattern_id="browser.element_not_found",
        description="Element not found on page",
        recovery_chain=[
            RecoveryStep("Get fresh snapshot to find correct refs", "browse_snapshot", None),
            RecoveryStep("Scroll down to reveal hidden elements", "browse_eval", {"expression": "window.scrollBy(0, 500)"}),
            RecoveryStep("Reload page and re-scan", "browse_open", None),
        ]
    ),
    "browser.type_fails": FailurePattern(
        pattern_id="browser.type_fails",
        description="Type action fails (React controlled input, shadow DOM)",
        recovery_chain=[
            RecoveryStep("Try filling with press_enter to submit", "browse_fill", {"press_enter": True}),
            RecoveryStep("JS injection via eval", "browse_eval", None),
            RecoveryStep("Click element first then fill", "browse_click", None),
        ]
    ),
    "browser.cdp_unavailable": FailurePattern(
        pattern_id="browser.cdp_unavailable",
        description="CDP port not open on Electron app",
        recovery_chain=[
            RecoveryStep("Launch app and try browser open with auto-connect", "browse_open", {"auto_connect": True}),
            RecoveryStep("Fall back to UIA desktop control", "pc_get_ui_tree", None),
        ]
    ),
    "browser.connection_refused": FailurePattern(
        pattern_id="browser.connection_refused",
        description="Browser not connected",
        recovery_chain=[
            RecoveryStep("Open browser with local mode (most reliable)", "browse_open", None),
            RecoveryStep("Take screenshot to check state", "browse_screenshot", None),
        ]
    ),
    "browser.no_active_page": FailurePattern(
        pattern_id="browser.no_active_page",
        description="No active page in session",
        recovery_chain=[
            RecoveryStep("Open a URL to create a page", "browse_open", None),
            RecoveryStep("Take snapshot after page loads", "browse_snapshot", None),
        ]
    ),
    "desktop.uia_timeout": FailurePattern(
        pattern_id="desktop.uia_timeout",
        description="pywinauto UIA operation timed out",
        recovery_chain=[
            RecoveryStep("Focus window first", "pc_focus", None),
            RecoveryStep("Re-scan UI tree", "pc_get_ui_tree", None),
            RecoveryStep("Use coordinate click fallback", "pc_click", None),
        ]
    ),
    "desktop.electron_no_cdp": FailurePattern(
        pattern_id="desktop.electron_no_cdp",
        description="Electron app has no CDP port",
        recovery_chain=[
            RecoveryStep("Use UIA accessibility tree instead", "pc_get_ui_tree", None),
            RecoveryStep("Launch with browser auto-connect", "browse_open", {"auto_connect": True}),
        ]
    ),
    "network.403_forbidden": FailurePattern(
        pattern_id="network.403_forbidden",
        description="HTTP 403 from target site (bot detection)",
        recovery_chain=[
            RecoveryStep("Try scrape with different user agent", "scrape", None),
            RecoveryStep("Use search to find alternative source", "search", None),
        ]
    ),
    "network.timeout": FailurePattern(
        pattern_id="network.timeout",
        description="Request timed out",
        recovery_chain=[
            RecoveryStep("Retry with fetch tool", "fetch", None),
            RecoveryStep("Use search for alternative", "search", None),
        ]
    ),
    "network.rate_limited": FailurePattern(
        pattern_id="network.rate_limited",
        description="HTTP 429 rate limit",
        recovery_chain=[
            RecoveryStep("Wait and retry", "run_command", {"command": "timeout 5"}),
            RecoveryStep("Use search for alternative", "search", None),
        ]
    ),
    "code.syntax_error": FailurePattern(
        pattern_id="code.syntax_error",
        description="Python syntax error in generated code",
        recovery_chain=[
            RecoveryStep("Read the file to see the error context", "read_file", None),
            RecoveryStep("Edit file to fix the syntax error", "edit_file", None),
            RecoveryStep("Re-execute after fix", "run_command", None),
        ]
    ),
    "code.import_error": FailurePattern(
        pattern_id="code.import_error",
        description="Missing Python package",
        recovery_chain=[
            RecoveryStep("Install missing package", "run_command", {"command": "pip install {package}"}),
            RecoveryStep("Retry execution after install", "run_command", None),
        ]
    ),
    "shell.interactive_timeout": FailurePattern(
        pattern_id="shell.interactive_timeout",
        description="Shell command timed out waiting for interactive input",
        recovery_chain=[
            RecoveryStep("Use non-interactive alternative", "run_command", None),
        ]
    ),
    "tool.not_found": FailurePattern(
        pattern_id="tool.not_found",
        description="Tool not found or not registered",
        recovery_chain=[
            RecoveryStep("Create the missing tool using create_tool", "create_tool", None),
            RecoveryStep("Use run_command to achieve the same result via shell", "run_command", None),
        ]
    ),
    "npm.failed": FailurePattern(
        pattern_id="npm.failed",
        description="npm/npx command failed",
        recovery_chain=[
            RecoveryStep("Check if Node.js is installed", "run_command", {"command": "node --version"}),
            RecoveryStep("Clear npm cache and retry", "run_command", {"command": "npm cache clean --force"}),
        ]
    ),
}


class FailureLibrary:
    ERROR_PATTERNS = [
        ("Element.*not found|element_id.*invalid", "browser.element_not_found"),
        ("type.*fail|nativeInputValueSetter", "browser.type_fails"),
        ("CDP.*not available|remote-debugging", "browser.cdp_unavailable"),
        ("Could not establish connection|content script", "browser.connection_refused"),
        ("No active page|no active session", "browser.no_active_page"),
        ("UIA.*timeout|automation timeout", "desktop.uia_timeout"),
        ("403.*Forbidden|Cloudflare|bot detected", "network.403_forbidden"),
        ("timed out.*interactive input|npm create.*timed out|waiting for interactive", "shell.interactive_timeout"),
        ("TimeoutError|timed out", "network.timeout"),
        ("429.*rate.*limit|Too Many Requests", "network.rate_limited"),
        ("SyntaxError|IndentationError", "code.syntax_error"),
        ("ImportError|ModuleNotFoundError", "code.import_error"),
        ("Tool.*not found|not registered", "tool.not_found"),
        ("npm ERR!|npx.*failed|exit 1.*npm", "npm.failed"),
    ]

    def __init__(self):
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._failure_timestamps: Dict[str, List[float]] = defaultdict(list)

    def classify(self, error_message: str) -> Optional[FailurePattern]:
        for pattern_str, pattern_id in self.ERROR_PATTERNS:
            if re.search(pattern_str, error_message, re.IGNORECASE):
                return FAILURE_TREE.get(pattern_id)
        return None

    def record_failure(self, pattern_id: str):
        """Record a failure occurrence for pattern tracking."""
        self._failure_counts[pattern_id] += 1
        self._failure_timestamps[pattern_id].append(time.time())
        # Keep only last 10 timestamps
        if len(self._failure_timestamps[pattern_id]) > 10:
            self._failure_timestamps[pattern_id] = self._failure_timestamps[pattern_id][-10:]

    def get_failure_count(self, pattern_id: str) -> int:
        """Get how many times this failure pattern has occurred."""
        return self._failure_counts.get(pattern_id, 0)

    def get_recovery_hint(self, error_message: str) -> str:
        pattern = self.classify(error_message)
        if not pattern:
            return ""

        # Record this failure
        self.record_failure(pattern.pattern_id)
        count = self.get_failure_count(pattern.pattern_id)

        steps = [f"{i+1}. {step.description}"
                 for i, step in enumerate(pattern.recovery_chain[:3])]
        hint = (
            f"[FAILURE LIBRARY] {pattern.description}. "
            f"Try in order: {'; '.join(steps)}"
        )

        # If repeated failure, add stronger warning
        if count >= 3:
            hint += f"\n⚠️ This error has occurred {count} times. Previous recovery steps may not work. Consider a different approach."
        elif count >= 2:
            hint += f"\n⚠️ This is the {count}nd time this error occurred. If recovery fails, try something different."

        return hint
