from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

import yaml

from core.types import CompiledAction

# Resolve config/codebook.yaml relative to project root
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_CODEBOOK_PATH = _CONFIG_DIR / "codebook.yaml"


class CodebookCompiler:
    """Compiles natural-language intents into structured action tokens.

    Loads action definitions from ``config/codebook.yaml`` at init.
    Falls back to a small hardcoded dict if the YAML file is missing.
    """

    def __init__(self, codebook: dict = None):
        if codebook is not None:
            self._codebook = codebook
        else:
            self._codebook = self._load_yaml()

    # ── public API ───────────────────────────────────────

    def compile(self, raw_intent: str) -> Optional[CompiledAction]:
        """Parse short natural-language intent into a CompiledAction.

        Designed for SHORT intent strings (2-10 words), not full LLM responses.
        For LLM responses, use regex-based ACT:TOKEN extraction instead.
        """
        intent_lower = raw_intent.lower().strip()
        best: Optional[CompiledAction] = None
        best_conf = 0.0

        for action in self._actions:
            score = self._match(action["patterns"], intent_lower)
            if score > best_conf:
                best_conf = score
                params = self._extract_params(action, raw_intent)
                best = CompiledAction(
                    token=action["token"],
                    params=params,
                    execution_target=action.get("target"),
                    confidence=min(score, 1.0),
                    raw_input=raw_intent,
                )

        return best

    def get_actions_for_manifest(self) -> list[dict]:
        """Return a flat list of action descriptors for ManifestBuilder."""
        return [
            {
                "token": a["token"],
                "description": a.get("description", ""),
                "target": a.get("target", "system"),
                "risk_level": a.get("risk_level", "low"),
                "params_schema": a.get("params_schema", {}),
                "patterns": a.get("patterns", []),
            }
            for a in self._actions
        ]

    def get_tools_schema(self) -> list[dict]:
        """Generate OpenAI-compatible tools schema from codebook.

        Each action becomes a function definition that the LLM can call natively.
        No regex parsing needed — the model returns structured JSON tool_calls.

        Grouped tools (have 'action' param): only 'action' is required.
        Simple tools: all params are required.

        Every tool includes an 'intent' parameter for display/summarization.
        """
        tools = []
        for action in self._actions:
            token = action["token"]
            func_name = token.replace("ACT:", "").lower()

            params_schema = action.get("params_schema", {})
            properties = {}
            required = []
            is_grouped = "action" in params_schema

            for param_name, param_type in params_schema.items():
                if param_type in ("string", "number", "array", "object", "boolean"):
                    prop = {"type": param_type}
                else:
                    prop = {"type": "string", "description": param_type}
                properties[param_name] = prop
                # Grouped tools: only action is required
                if is_grouped:
                    if param_name == "action":
                        required.append(param_name)
                else:
                    required.append(param_name)

            # Add intent field for display/summarization
            properties["intent"] = {
                "type": "string",
                "description": "Brief description of what you're doing (for display)"
            }

            tool = {
                "type": "function",
                "function": {
                    "name": func_name,
                    "description": action.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
            tools.append(tool)
        return tools

    def get_risk_levels(self) -> dict[str, str]:
        """Return mapping of function name -> risk level."""
        risks = {}
        for action in self._actions:
            func_name = action["token"].replace("ACT:", "").lower()
            risks[func_name] = action.get("risk_level", "low")
        return risks

    # ── internals ────────────────────────────────────────

    @staticmethod
    def _match(patterns: list[str], text: str) -> float:
        """Return a confidence score 0-1 based on how many patterns match.

        Any single match gives 0.75. More matches scale up to 1.0.
        """
        if not patterns:
            return 0.0
        hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        if hits == 0:
            return 0.0
        return 0.6 + 0.4 * (hits / len(patterns))

    @staticmethod
    def _extract_params(action: dict, raw: str) -> dict:
        """Best-effort parameter extraction from raw intent."""
        params: dict = {}
        schema = action.get("params_schema", {})

        # Pull a quoted string if present
        quoted = re.findall(r'["\']([^"\']+)["\']', raw)

        for key in schema:
            if key == "path" and quoted:
                params["path"] = quoted[0]
            elif key == "url":
                urls = re.findall(r"https?://\S+", raw)
                params["url"] = urls[0] if urls else (quoted[0] if quoted else raw)
            elif key in ("query", "text", "content", "code", "command", "subcommand"):
                params[key] = raw

        return params

    def _load_yaml(self) -> dict:
        """Load codebook.yaml and return internal dict keyed by compiled regex."""
        if not _CODEBOOK_PATH.exists():
            return self._fallback_codebook()

        with open(_CODEBOOK_PATH, "r", encoding="utf-8") as fh:
            actions = yaml.safe_load(fh)

        if not isinstance(actions, list):
            return self._fallback_codebook()

        self._actions: list[dict] = actions
        # Return a dict keyed by first pattern for backward compat with tests
        result: dict = {}
        for action in actions:
            for pat in action.get("patterns", []):
                result[pat] = action
        return result

    def _fallback_codebook(self) -> dict:
        """Minimal hardcoded codebook — used only if YAML is missing."""
        self._actions = [
            {
                "token": "ACT:CLICK",
                "patterns": [r"\bclick\b", r"\bpress\b", r"\btap\b"],
                "target": "webmcp",
                "description": "Click an element",
                "params_schema": {"element": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:TYPE",
                "patterns": [r"\btype\b", r"\binput\b", r"\benter text\b"],
                "target": "webmcp",
                "description": "Type text into a field",
                "params_schema": {"text": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:SCROLL",
                "patterns": [r"\bscroll\b", r"\bswipe\b"],
                "target": "webmcp",
                "description": "Scroll the page",
                "params_schema": {"direction": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:NAVIGATE",
                "patterns": [r"\bnavigate\b", r"\bgo to\b", r"\bopen url\b"],
                "target": "webmcp",
                "description": "Navigate to a URL",
                "params_schema": {"url": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:WEB_SEARCH",
                "patterns": [r"\bsearch\b", r"\bfind\b", r"\blook up\b"],
                "target": "webmcp",
                "description": "Search the web",
                "params_schema": {"query": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:READ_FILE",
                "patterns": [r"\bread file\b", r"\bopen file\b"],
                "target": "file",
                "description": "Read a file",
                "params_schema": {"path": "string"},
                "risk_level": "low",
            },
            {
                "token": "ACT:WRITE_FILE",
                "patterns": [r"\bwrite\b", r"\bsave\b", r"\bcreate file\b"],
                "target": "file",
                "description": "Write a file",
                "params_schema": {"path": "string", "content": "string"},
                "risk_level": "medium",
            },
            {
                "token": "ACT:SHELL",
                "patterns": [r"\brun\b", r"\bexecute\b", r"\bshell\b"],
                "target": "shell",
                "description": "Run a shell command",
                "params_schema": {"command": "string"},
                "risk_level": "high",
            },
        ]
        return {a["patterns"][0]: a for a in self._actions}
