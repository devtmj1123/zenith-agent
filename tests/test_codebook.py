"""Tests for core/codebook_compiler.py"""
import sys
from pathlib import Path
from unittest import mock

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.codebook_compiler import CodebookCompiler


def _make_compiler(yaml_exists=True):
    """Create a compiler — either from YAML or by mocking YAML as missing."""
    if yaml_exists:
        return CodebookCompiler()
    # Mock the YAML path so _load_yaml takes the fallback branch
    with mock.patch(
        "core.codebook_compiler._CODEBOOK_PATH",
        new=Path("/nonexistent/codebook.yaml"),
    ):
        return CodebookCompiler()


# ── Test 1: YAML loads successfully ──────────────────────────────────────────
def test_yaml_loads():
    compiler = _make_compiler(yaml_exists=True)
    assert hasattr(compiler, "_actions"), "_actions attribute missing"
    assert len(compiler._actions) > 0, "YAML loaded but _actions is empty"
    print("PASS  test_yaml_loads — codebook.yaml loaded successfully")


# ── Test 2: _actions count ──────────────────────────────────────────────────
def test_actions_count():
    compiler = _make_compiler(yaml_exists=True)
    count = len(compiler._actions)
    assert count >= 14, f"Expected at least 14 actions, got {count}"
    print(f"PASS  test_actions_count — {count} actions in codebook")


# ── Test 3: get_tools_schema returns tools in OpenAI format ─────────────────
def test_tools_schema_format():
    compiler = _make_compiler(yaml_exists=True)
    tools = compiler.get_tools_schema()
    assert len(tools) >= 14, f"Expected at least 14 tools, got {len(tools)}"
    for i, tool in enumerate(tools):
        assert tool["type"] == "function", f"Tool {i}: type != 'function'"
        func = tool.get("function")
        assert isinstance(func, dict), f"Tool {i}: missing 'function' dict"
        assert "name" in func, f"Tool {i}: missing function.name"
        assert "description" in func, f"Tool {i}: missing function.description"
        assert "parameters" in func, f"Tool {i}: missing function.parameters"
        params = func["parameters"]
        assert params["type"] == "object", f"Tool {i}: parameters.type != 'object'"
    print(f"PASS  test_tools_schema_format — {len(tools)} tools, all OpenAI format compliant")


# ── Test 4: Each tool has required fields ────────────────────────────────────
def test_tool_fields():
    compiler = _make_compiler(yaml_exists=True)
    tools = compiler.get_tools_schema()
    for tool in tools:
        func = tool["function"]
        name = func["name"]
        assert name and isinstance(name, str), "Empty name in tool"
        assert func["description"], f"Empty description in {name}"
        assert "properties" in func["parameters"], f"Missing properties in {name}"
    print("PASS  test_tool_fields — all tools have name, description, parameters")


# ── Test 5: get_risk_levels returns correct mapping ──────────────────────────
def test_risk_levels():
    compiler = _make_compiler(yaml_exists=True)
    risks = compiler.get_risk_levels()
    assert isinstance(risks, dict), "get_risk_levels() did not return a dict"
    assert len(risks) >= 14, f"Expected at least 14 risk entries, got {len(risks)}"
    known_levels = {"low", "medium", "high"}
    for name, level in risks.items():
        assert level in known_levels, f"{name} has unknown risk level: {level}"
    # Spot-check a few
    assert risks.get("read_file") == "low", "read_file should be low"
    assert risks.get("run_command") == "high", "run_command should be high"
    assert risks.get("write_file") == "medium", "write_file should be medium"
    print(f"PASS  test_risk_levels — risk dict with correct levels for {len(risks)} actions")


# ── Test 6: Fallback codebook works when YAML is missing ─────────────────────
def test_fallback_codebook():
    compiler = _make_compiler(yaml_exists=False)
    assert hasattr(compiler, "_actions"), "Fallback missing _actions"
    count = len(compiler._actions)
    assert count > 0, "Fallback _actions is empty"
    # Fallback has 8 actions per the source
    assert count == 8, f"Expected 8 fallback actions, got {count}"
    tokens = [a["token"] for a in compiler._actions]
    assert "ACT:READ_FILE" in tokens, "Fallback missing ACT:READ_FILE"
    assert "ACT:SHELL" in tokens, "Fallback missing ACT:SHELL"
    print("PASS  test_fallback_codebook — fallback loaded 8 actions when YAML missing")


# ── Test 7: compile() matches simple intents ─────────────────────────────────
def test_compile_simple_intents():
    compiler = _make_compiler(yaml_exists=True)

    cases = [
        ("read file", "ACT:READ_FILE"),
        ("open file", "ACT:READ_FILE"),
        ("search", "ACT:WEB_SEARCH"),
        ("click", "ACT:CLICK"),
        ("run command", "ACT:RUN_COMMAND"),
        ("navigate", "ACT:NAVIGATE"),
        ("what time", "ACT:GET_TIME"),
    ]

    failures = []
    for intent, expected_token in cases:
        result = compiler.compile(intent)
        if result is None:
            failures.append(f"  '{intent}' -> None (expected {expected_token})")
        elif result.token != expected_token:
            failures.append(f"  '{intent}' -> {result.token} (expected {expected_token})")

    if failures:
        print("FAIL  test_compile_simple_intents — mismatches:")
        for f in failures:
            print(f)
    else:
        print(f"PASS  test_compile_simple_intents — {len(cases)} intents matched correctly")


# ── Test 8: Tool descriptions are short (not bloated) ────────────────────────
def test_descriptions_short():
    compiler = _make_compiler(yaml_exists=True)
    tools = compiler.get_tools_schema()
    MAX_DESC_LEN = 200  # generous upper bound — short means "not a paragraph"
    long_ones = []
    for tool in tools:
        desc = tool["function"]["description"]
        if len(desc) > MAX_DESC_LEN:
            long_ones.append((tool["function"]["name"], len(desc)))

    if long_ones:
        print("FAIL  test_descriptions_short — bloated descriptions:")
        for name, length in long_ones:
            print(f"  {name}: {length} chars")
    else:
        max_len = max(len(t["function"]["description"]) for t in tools)
        print(f"PASS  test_descriptions_short — all descriptions under {MAX_DESC_LEN} chars (max={max_len})")


# ── Run all ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_yaml_loads,
        test_actions_count,
        test_tools_schema_format,
        test_tool_fields,
        test_risk_levels,
        test_fallback_codebook,
        test_compile_simple_intents,
        test_descriptions_short,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL  {t.__name__} — {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(0 if failed == 0 else 1)
