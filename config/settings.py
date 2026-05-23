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
        "model_env": "OPENAI_MODEL",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "env_key": "NVIDIA_API_KEY",
        "model_env": "NVIDIA_MODEL",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2:3b",
        "env_key": None,
        "model_env": "OLLAMA_MODEL",
    },
}


def _resolve_model(provider_name: str) -> str:
    """
    Model resolution priority:
    1. ZENITH_MODEL (global override)
    2. PROVIDER_MODEL (e.g. GROQ_MODEL, NVIDIA_MODEL)
    3. Provider default
    """
    global_override = os.getenv("ZENITH_MODEL", "").strip()
    if global_override:
        return global_override

    preset = PROVIDERS.get(provider_name, {})
    provider_override = os.getenv(preset.get("model_env", ""), "").strip()
    if provider_override:
        return provider_override

    return preset.get("model", "")


class Settings:
    def __init__(self):
        # Main LLM
        self.provider = "groq"
        self.llm_model = ""
        self.llm_api_key = ""
        self.llm_base_url = ""

        # Compressor LLM (fast local model)
        self.compressor_provider = "ollama"
        self.compressor_model = ""
        self.compressor_api_key = ""
        self.compressor_base_url = ""

        # General
        self.token_budget = 50_000
        self.max_iterations = 30
        self.debug = False
        self.tts_enabled = False
        self.tts_engine = "edge"
        self.ollama_url = "http://localhost:11434"

    def load_from_env(self):
        # Main provider
        self.provider = os.getenv("ZENITH_PROVIDER", self.provider).lower()
        preset = PROVIDERS.get(self.provider, PROVIDERS["groq"])
        self.llm_base_url = os.getenv("ZENITH_BASE_URL") or preset["base_url"]
        self.llm_model = _resolve_model(self.provider)
        if preset["env_key"]:
            self.llm_api_key = os.getenv("ZENITH_API_KEY", os.getenv(preset["env_key"], ""))
        else:
            self.llm_api_key = os.getenv("ZENITH_API_KEY", "")

        # Compressor provider (default: ollama for fast local compression)
        self.compressor_provider = os.getenv("COMPRESS_PROVIDER", "ollama").lower()
        compress_preset = PROVIDERS.get(self.compressor_provider, PROVIDERS["ollama"])
        self.compressor_base_url = os.getenv("COMPRESS_BASE_URL") or compress_preset["base_url"]
        self.compressor_model = os.getenv("COMPRESS_MODEL") or _resolve_model(self.compressor_provider)
        if compress_preset["env_key"]:
            self.compressor_api_key = os.getenv(
                "COMPRESS_API_KEY",
                os.getenv(compress_preset["env_key"], "")
            )
        else:
            self.compressor_api_key = ""

        self.debug = os.getenv("ZENITH_DEBUG", "").lower() in ("1", "true", "yes")

    def resolve_provider(self, name: str):
        """Switch main provider by name."""
        name = name.lower()
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
        self.provider = name
        preset = PROVIDERS[name]
        self.llm_base_url = preset["base_url"]
        self.llm_model = _resolve_model(name)
        if preset["env_key"]:
            self.llm_api_key = os.getenv(preset["env_key"], os.getenv("ZENITH_API_KEY", ""))

    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return True
        return bool(self.llm_api_key)
