from __future__ import annotations
from pathlib import Path
from typing import Optional


class Settings:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.llm_provider = "openai"
        self.llm_model = "gpt-4o-mini"
        self.llm_api_key = ""
        self.llm_base_url = "https://api.openai.com/v1"
        self.token_budget = 50_000
        self.max_iterations = 30
        self.debug = False
        self.tts_enabled = False
        self.tts_engine = "edge"
        self.ollama_model = "llama3.2:3b"
        self.ollama_url = "http://localhost:11434"

    def load_from_env(self):
        import os
        self.llm_api_key = os.getenv("ZENITH_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.llm_base_url = os.getenv("ZENITH_BASE_URL", self.llm_base_url)
        self.llm_model = os.getenv("ZENITH_MODEL", self.llm_model)
        self.debug = os.getenv("ZENITH_DEBUG", "").lower() in ("1", "true", "yes")

    def load_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
