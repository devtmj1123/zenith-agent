from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


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


class Settings:
    def __init__(self):
        self.provider = "groq"             # default: fast + free tier
        self.llm_model = ""
        self.llm_api_key = ""
        self.llm_base_url = ""
        self.token_budget = 50_000
        self.max_iterations = 30
        self.debug = False
        self.tts_enabled = False
        self.tts_engine = "edge"
        self.ollama_url = "http://localhost:11434"

    def load_from_env(self):
        # Provider selection
        self.provider = os.getenv("ZENITH_PROVIDER", self.provider).lower()

        # Apply provider defaults
        preset = PROVIDERS.get(self.provider, PROVIDERS["groq"])
        self.llm_base_url = os.getenv("ZENITH_BASE_URL", preset["base_url"])
        self.llm_model = os.getenv("ZENITH_MODEL", preset["model"])

        # API key: explicit env var > provider-specific env var
        if preset["env_key"]:
            self.llm_api_key = os.getenv(
                "ZENITH_API_KEY",
                os.getenv(preset["env_key"], "")
            )
        else:
            self.llm_api_key = os.getenv("ZENITH_API_KEY", "")

        self.debug = os.getenv("ZENITH_DEBUG", "").lower() in ("1", "true", "yes")

    def resolve_provider(self, name: str):
        """Switch provider by name."""
        name = name.lower()
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
        self.provider = name
        preset = PROVIDERS[name]
        self.llm_base_url = preset["base_url"]
        self.llm_model = preset["model"]
        if preset["env_key"]:
            self.llm_api_key = os.getenv(preset["env_key"], os.getenv("ZENITH_API_KEY", ""))

    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return True  # no key needed
        return bool(self.llm_api_key)
