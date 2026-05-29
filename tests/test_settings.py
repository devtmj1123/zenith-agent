"""Test suite for config/settings.py — 9 test cases."""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _clean_env():
    """Remove all provider-related env vars to get a clean slate."""
    keys = [
        "REASONING_PROVIDER", "REASONING_MODEL", "REASONING_API_KEY",
        "COMPRESSION_PROVIDER", "COMPRESSION_MODEL", "COMPRESSION_API_KEY",
        "FAST_PATH_PROVIDER", "FAST_PATH_MODEL", "FAST_PATH_API_KEY",
        "MIMO_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY",
        "ZENITH_DEBUG",
    ]
    for k in keys:
        os.environ.pop(k, None)


# ──────────────────────────────────────────────
# Test 1: Settings.load_from_env() reads .env
# ──────────────────────────────────────────────
def test_1_load_from_env():
    """
    Verify that load_from_env() populates Settings from environment variables.
    We set REASONING_PROVIDER=mimo + MIMO_API_KEY and check the object.
    """
    _clean_env()
    os.environ["REASONING_PROVIDER"] = "mimo"
    os.environ["MIMO_API_KEY"] = "test-key-123"

    # Must re-import so the module-level .env loading doesn't interfere
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    s = settings_mod.Settings()
    s.load_from_env()

    assert s.reasoning.provider == "mimo", f"Expected provider 'mimo', got '{s.reasoning.provider}'"
    assert s.reasoning.api_key == "test-key-123", f"Expected api_key 'test-key-123', got '{s.reasoning.api_key}'"
    assert s.reasoning.base_url == "https://api.xiaomimimo.com/v1", f"Wrong base_url: {s.reasoning.base_url}"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 2: ModelRole fields for mimo provider
# ──────────────────────────────────────────────
def test_2_model_role_mimo():
    """ModelRole created with mimo preset has correct provider/model/api_key/base_url."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()
    os.environ["REASONING_PROVIDER"] = "mimo"
    os.environ["MIMO_API_KEY"] = "sk-mimo-test"

    s = settings_mod.Settings()
    s.load_from_env()
    r = s.reasoning

    assert r.provider == "mimo"
    assert r.model == "MiMo-v2.5", f"Expected model 'MiMo-v2.5', got '{r.model}'"
    assert r.api_key == "sk-mimo-test"
    assert r.base_url == "https://api.xiaomimimo.com/v1"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 3: PROVIDERS dict has all 5 providers
# ──────────────────────────────────────────────
def test_3_providers_dict():
    """PROVIDERS contains openai, groq, nvidia, ollama, mimo, cerebras."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    expected = {"openai", "groq", "nvidia", "ollama", "mimo", "cerebras"}
    actual = set(settings_mod.PROVIDERS.keys())
    missing = expected - actual
    assert not missing, f"Missing providers: {missing}"
    assert len(settings_mod.PROVIDERS) == 6, f"Expected 6 providers, got {len(settings_mod.PROVIDERS)}"
    return "PASS"


# ──────────────────────────────────────────────
# Test 4: Mimo provider base_url and env_key
# ──────────────────────────────────────────────
def test_4_mimo_provider_config():
    """Mimo provider entry: base_url=https://api.xiaomimimo.com/v1, env_key=MIMO_API_KEY."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    mimo = settings_mod.PROVIDERS["mimo"]
    assert mimo["base_url"] == "https://api.xiaomimimo.com/v1", f"Wrong base_url: {mimo['base_url']}"
    assert mimo["env_key"] == "MIMO_API_KEY", f"Wrong env_key: {mimo['env_key']}"
    return "PASS"


# ──────────────────────────────────────────────
# Test 5: _get_api_key("mimo") reads MIMO_API_KEY
# ──────────────────────────────────────────────
def test_5_get_api_key_mimo():
    """_get_api_key('mimo') returns whatever MIMO_API_KEY is set to."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()
    os.environ["MIMO_API_KEY"] = "my-secret-mimo-key"

    result = settings_mod._get_api_key("mimo")
    assert result == "my-secret-mimo-key", f"Expected 'my-secret-mimo-key', got '{result}'"

    # Also test empty when not set
    os.environ.pop("MIMO_API_KEY", None)
    result2 = settings_mod._get_api_key("mimo")
    assert result2 == "", f"Expected empty string when unset, got '{result2}'"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 6: _resolve_model("mimo", "REASONING_MODEL")
# ──────────────────────────────────────────────
def test_6_resolve_model_mimo():
    """_resolve_model returns default model when no override env is set, and override when it is."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()

    # No override -> provider default
    result = settings_mod._resolve_model("mimo", "REASONING_MODEL")
    assert result == "MiMo-v2.5", f"Expected default 'MiMo-v2.5', got '{result}'"

    # With override
    os.environ["REASONING_MODEL"] = "custom-mimo-model"
    result2 = settings_mod._resolve_model("mimo", "REASONING_MODEL")
    assert result2 == "custom-mimo-model", f"Expected override 'custom-mimo-model', got '{result2}'"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 7: Settings.is_configured() with API key
# ──────────────────────────────────────────────
def test_7_is_configured():
    """is_configured() returns True when the reasoning role has an API key."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()
    os.environ["REASONING_PROVIDER"] = "mimo"
    os.environ["MIMO_API_KEY"] = "valid-key"

    s = settings_mod.Settings()
    s.load_from_env()
    assert s.is_configured() is True, "Expected is_configured()=True when key is set"

    # Without key -> False
    _clean_env()
    os.environ["REASONING_PROVIDER"] = "mimo"
    s2 = settings_mod.Settings()
    s2.load_from_env()
    assert s2.is_configured() is False, "Expected is_configured()=False when key is empty"

    # Ollama always configured (no key needed)
    _clean_env()
    os.environ["REASONING_PROVIDER"] = "ollama"
    s3 = settings_mod.Settings()
    s3.load_from_env()
    assert s3.is_configured() is True, "Expected is_configured()=True for ollama (no key needed)"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 8: resolve_provider() switches reasoning
# ──────────────────────────────────────────────
def test_8_resolve_provider():
    """resolve_provider() re-creates the reasoning ModelRole for the new provider."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()
    os.environ["MIMO_API_KEY"] = "mimo-key"
    os.environ["GROQ_API_KEY"] = "groq-key"

    s = settings_mod.Settings()
    s.load_from_env()

    # Switch to mimo
    s.resolve_provider("mimo")
    assert s.reasoning.provider == "mimo", f"Expected 'mimo', got '{s.reasoning.provider}'"
    assert s.reasoning.base_url == "https://api.xiaomimimo.com/v1"
    assert s.reasoning.model == "MiMo-v2.5"
    assert s.reasoning.api_key == "mimo-key"

    # Switch back to groq
    s.resolve_provider("groq")
    assert s.reasoning.provider == "groq", f"Expected 'groq', got '{s.reasoning.provider}'"
    assert s.reasoning.base_url == "https://api.groq.com/openai/v1"
    assert s.reasoning.api_key == "groq-key"

    # Unknown provider raises ValueError
    try:
        s.resolve_provider("nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Test 9: Backward compat aliases sync correctly
# ──────────────────────────────────────────────
def test_9_backward_compat_aliases():
    """After load_from_env(), legacy attributes mirror the ModelRole fields."""
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    _clean_env()
    os.environ["REASONING_PROVIDER"] = "mimo"
    os.environ["MIMO_API_KEY"] = "alias-test-key"
    os.environ["COMPRESSION_PROVIDER"] = "ollama"

    s = settings_mod.Settings()
    s.load_from_env()

    # Reasoning aliases
    assert s.provider == s.reasoning.provider, f"provider mismatch: {s.provider} != {s.reasoning.provider}"
    assert s.llm_model == s.reasoning.model, f"llm_model mismatch: {s.llm_model} != {s.reasoning.model}"
    assert s.llm_api_key == s.reasoning.api_key, f"llm_api_key mismatch"
    assert s.llm_base_url == s.reasoning.base_url, f"llm_base_url mismatch"

    # Compression aliases
    assert s.compressor_provider == s.compression.provider
    assert s.compressor_model == s.compression.model
    assert s.compressor_api_key == s.compression.api_key
    assert s.compressor_base_url == s.compression.base_url

    # After resolve_provider, aliases should update too
    os.environ["GROQ_API_KEY"] = "groovy"
    s.resolve_provider("groq")
    assert s.provider == "groq", f"After resolve_provider, provider should be 'groq', got '{s.provider}'"
    assert s.llm_base_url == "https://api.groq.com/openai/v1"

    _clean_env()
    return "PASS"


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("1. load_from_env() reads .env",                    test_1_load_from_env),
        ("2. ModelRole fields for mimo provider",             test_2_model_role_mimo),
        ("3. PROVIDERS dict has all 5 providers",             test_3_providers_dict),
        ("4. Mimo provider base_url + env_key",               test_4_mimo_provider_config),
        ("5. _get_api_key('mimo') returns MIMO_API_KEY",      test_5_get_api_key_mimo),
        ("6. _resolve_model('mimo', 'REASONING_MODEL')",      test_6_resolve_model_mimo),
        ("7. is_configured() with API key set",               test_7_is_configured),
        ("8. resolve_provider() switches reasoning",          test_8_resolve_provider),
        ("9. Backward compat aliases sync correctly",         test_9_backward_compat_aliases),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}  -->  {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(1 if failed else 0)
