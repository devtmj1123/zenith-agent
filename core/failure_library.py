from __future__ import annotations
import re
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
        description="Element ID not found on page",
        recovery_chain=[
            RecoveryStep("Scroll down to reveal hidden elements", "ACT:SCROLL", {"direction": "down"}),
            RecoveryStep("Reload page and re-scan elements", "ACT:NAVIGATE", None),
            RecoveryStep("Get elements with broader selector", "ACT:GET_ELEMENTS", {"options": {"include_hidden": True}}),
            RecoveryStep("Use CSS selector instead of element_id", "ACT:CLICK", None),
        ]
    ),
    "browser.type_fails": FailurePattern(
        pattern_id="browser.type_fails",
        description="Type action fails (React controlled input, shadow DOM)",
        recovery_chain=[
            RecoveryStep("Clipboard paste (bypasses React onChange)", "ACT:SHELL", {"command": "echo '{text}' | clip"}),
            RecoveryStep("JS injection via evaluate", "ACT:SHELL", None),
            RecoveryStep("Focus element then keyboard simulation", "ACT:PRESS_KEY", {"key": "TAB"}),
        ]
    ),
    "browser.cdp_unavailable": FailurePattern(
        pattern_id="browser.cdp_unavailable",
        description="CDP port not open on Electron app",
        recovery_chain=[
            RecoveryStep("Launch Electron app with CDP via ElectronLauncher", "ACT:SHELL", None),
            RecoveryStep("Fall back to UIA accessibility tree", "ACT:GET_UI", None),
            RecoveryStep("Use browser web version instead", "ACT:NAVIGATE", None),
        ]
    ),
    "browser.connection_refused": FailurePattern(
        pattern_id="browser.connection_refused",
        description="Content script not connected",
        recovery_chain=[
            RecoveryStep("Wait 1.5s and retry", "ACT:SHELL", {"command": "ping -n 1 localhost"}),
            RecoveryStep("Reload tab to re-inject content script", "ACT:NAVIGATE", None),
            RecoveryStep("Open new tab and re-navigate", "ACT:NEW_TAB", None),
        ]
    ),
    "desktop.uia_timeout": FailurePattern(
        pattern_id="desktop.uia_timeout",
        description="pywinauto UIA operation timed out",
        recovery_chain=[
            RecoveryStep("Focus window first, then retry", "ACT:WIN_KEY", {"key": "ALT+TAB"}),
            RecoveryStep("Re-scan UI tree", "ACT:GET_UI", None),
            RecoveryStep("Use mouse coordinate fallback", "ACT:SHELL", {"command": "python -c 'import pyautogui; pyautogui.click(x,y)'"}),
        ]
    ),
    "desktop.electron_no_cdp": FailurePattern(
        pattern_id="desktop.electron_no_cdp",
        description="Electron app has no CDP port",
        recovery_chain=[
            RecoveryStep("Use ElectronLauncher to restart with CDP", "ACT:SHELL", None),
            RecoveryStep("Use UIA accessibility tree instead", "ACT:GET_UI", None),
        ]
    ),
    "network.403_forbidden": FailurePattern(
        pattern_id="network.403_forbidden",
        description="HTTP 403 from target site (bot detection)",
        recovery_chain=[
            RecoveryStep("Retry via Playwright headless (Tier 2)", "ACT:SCRAPE", {"action": "fetch", "tier": 2}),
            RecoveryStep("Retry via Firecrawl API (Tier 3)", "ACT:SCRAPE", {"action": "fetch", "tier": 3}),
            RecoveryStep("Use Chrome extension with real session (Tier 4)", "ACT:NAVIGATE", None),
        ]
    ),
    "network.timeout": FailurePattern(
        pattern_id="network.timeout",
        description="Request timed out",
        recovery_chain=[
            RecoveryStep("Retry with exponential backoff (2s)", "ACT:SHELL", {"command": "ping -n 1 8.8.8.8"}),
            RecoveryStep("Retry with increased timeout", "ACT:SCRAPE", {"timeout": 60}),
            RecoveryStep("Use cached/alternative source", "ACT:WEB_SEARCH", None),
        ]
    ),
    "network.rate_limited": FailurePattern(
        pattern_id="network.rate_limited",
        description="HTTP 429 rate limit",
        recovery_chain=[
            RecoveryStep("Wait 5 seconds", "ACT:SHELL", {"command": "ping -n 5 localhost"}),
            RecoveryStep("Switch to alternative endpoint", "ACT:WEB_SEARCH", None),
        ]
    ),
    "code.syntax_error": FailurePattern(
        pattern_id="code.syntax_error",
        description="Python syntax error in generated code",
        recovery_chain=[
            RecoveryStep("Read the file to see the error context", "ACT:READ_FILE", None),
            RecoveryStep("Edit file to fix the syntax error", "ACT:EDIT_FILE", None),
            RecoveryStep("Re-execute after fix", "ACT:CODE_EXEC", None),
        ]
    ),
    "code.import_error": FailurePattern(
        pattern_id="code.import_error",
        description="Missing Python package",
        recovery_chain=[
            RecoveryStep("Install missing package", "ACT:SHELL", {"command": "pip install {package} --break-system-packages"}),
            RecoveryStep("Retry execution after install", "ACT:CODE_EXEC", None),
        ]
    ),
}


class FailureLibrary:
    ERROR_PATTERNS = [
        ("Element.*not found|element_id.*invalid", "browser.element_not_found"),
        ("type.*fail|nativeInputValueSetter", "browser.type_fails"),
        ("CDP.*not available|remote-debugging", "browser.cdp_unavailable"),
        ("Could not establish connection|content script", "browser.connection_refused"),
        ("UIA.*timeout|automation timeout", "desktop.uia_timeout"),
        ("403.*Forbidden|Cloudflare|bot detected", "network.403_forbidden"),
        ("TimeoutError|timed out", "network.timeout"),
        ("429.*rate.*limit|Too Many Requests", "network.rate_limited"),
        ("SyntaxError|IndentationError", "code.syntax_error"),
        ("ImportError|ModuleNotFoundError", "code.import_error"),
    ]

    def classify(self, error_message: str) -> Optional[FailurePattern]:
        for pattern_str, pattern_id in self.ERROR_PATTERNS:
            if re.search(pattern_str, error_message, re.IGNORECASE):
                return FAILURE_TREE.get(pattern_id)
        return None

    def get_recovery_hint(self, error_message: str) -> str:
        pattern = self.classify(error_message)
        if not pattern:
            return ""
        steps = [f"{i+1}. {step.description}"
                 for i, step in enumerate(pattern.recovery_chain[:3])]
        return (
            f"[FAILURE LIBRARY] {pattern.description}. "
            f"Try in order: {'; '.join(steps)}"
        )
