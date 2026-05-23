from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

# Auto-load .env file if it exists
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


# Provider presets — base_url + default model
PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "env_key": "NVIDIA_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2:3b",
        "env_key": None,
    },
}


def _get_api_key(provider: str) -> str:
    """Get API key for a provider. Checks provider-specific key first, then shared."""
    preset = PROVIDERS.get(provider, {})
    env_key = preset.get("env_key")
    if env_key:
        return os.getenv(env_key, "")
    return ""  # ollama needs no key


def _resolve_model(provider: str, role_env: str = "") -> str:
    """
    Model resolution:
    1. Role-specific env (REASONING_MODEL, COMPRESSION_MODEL, FAST_PATH_MODEL)
    2. Provider default
    """
    if role_env:
        override = os.getenv(role_env, "").strip()
        if override:
            return override
    return PROVIDERS.get(provider, {}).get("model", "")


class ModelRole:
    """One model role: provider + model + api_key + base_url."""
    def __init__(self, provider: str, model: str, api_key: str, base_url: str):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return True
        return bool(self.api_key)


class Settings:
    def __init__(self):
        # 3 model roles
        self.reasoning: ModelRole = ModelRole("groq", "", "", "")
        self.compression: ModelRole = ModelRole("ollama", "", "", "")
        self.fast_path: ModelRole = ModelRole("ollama", "", "", "")

        # General
        self.token_budget = 50_000
        self.max_iterations = 30
        self.debug = False
        self.tts_enabled = False
        self.tts_engine = "edge"

        # Backward compat aliases (used by agent_loop, main.py old code)
        self.provider = ""
        self.llm_model = ""
        self.llm_api_key = ""
        self.llm_base_url = ""
        self.compressor_provider = ""
        self.compressor_model = ""
        self.compressor_api_key = ""
        self.compressor_base_url = ""

    def load_from_env(self):
        # --- REASONING ---
        r_prov = os.getenv("REASONING_PROVIDER", "groq").lower()
        r_preset = PROVIDERS.get(r_prov, PROVIDERS["groq"])
        self.reasoning = ModelRole(
            provider=r_prov,
            model=_resolve_model(r_prov, "REASONING_MODEL"),
            api_key=os.getenv("REASONING_API_KEY") or _get_api_key(r_prov),
            base_url=r_preset["base_url"],
        )

        # --- COMPRESSION ---
        c_prov = os.getenv("COMPRESSION_PROVIDER", "ollama").lower()
        c_preset = PROVIDERS.get(c_prov, PROVIDERS["ollama"])
        self.compression = ModelRole(
            provider=c_prov,
            model=_resolve_model(c_prov, "COMPRESSION_MODEL"),
            api_key=os.getenv("COMPRESSION_API_KEY") or _get_api_key(c_prov),
            base_url=c_preset["base_url"],
        )

        # --- FAST PATH ---
        f_prov = os.getenv("FAST_PATH_PROVIDER", "ollama").lower()
        f_preset = PROVIDERS.get(f_prov, PROVIDERS["ollama"])
        self.fast_path = ModelRole(
            provider=f_prov,
            model=_resolve_model(f_prov, "FAST_PATH_MODEL"),
            api_key=os.getenv("FAST_PATH_API_KEY") or _get_api_key(f_prov),
            base_url=f_preset["base_url"],
        )

        self.debug = os.getenv("ZENITH_DEBUG", "").lower() in ("1", "true", "yes")

        # Backward compat aliases
        self._sync_aliases()

    def _sync_aliases(self):
        """Keep old attribute names working for existing code."""
        self.provider = self.reasoning.provider
        self.llm_model = self.reasoning.model
        self.llm_api_key = self.reasoning.api_key
        self.llm_base_url = self.reasoning.base_url
        self.compressor_provider = self.compression.provider
        self.compressor_model = self.compression.model
        self.compressor_api_key = self.compression.api_key
        self.compressor_base_url = self.compression.base_url

    def resolve_provider(self, name: str):
        """Switch reasoning provider by name."""
        name = name.lower()
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
        preset = PROVIDERS[name]
        self.reasoning = ModelRole(
            provider=name,
            model=preset["model"],
            api_key=_get_api_key(name),
            base_url=preset["base_url"],
        )
        self._sync_aliases()

    def is_configured(self) -> bool:
        return self.reasoning.is_configured()
