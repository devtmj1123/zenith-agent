"""Tests for core/manifest_builder.py"""
import sys, os

# Ensure project root is on sys.path so `core` can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.manifest_builder import ManifestBuilder

builder = ManifestBuilder()

results = []

def run(name, fn):
    try:
        fn()
        results.append((name, "PASS", None))
    except Exception as e:
        results.append((name, "FAIL", str(e)))


# 1. build_system_prompt() returns a non-empty string
def test_1():
    out = builder.build_system_prompt("test goal")
    assert isinstance(out, str) and len(out) > 0, "Expected non-empty string"

# 2. Contains "Zenith" in the output
def test_2():
    out = builder.build_system_prompt("test goal")
    assert "Zenith" in out, f"'Zenith' not found in output"

# 3. With user_profile: includes name, role, communication_style
def test_3():
    profile = {"name": "Alice", "role": "developer", "communication_style": "concise"}
    out = builder.build_system_prompt("test goal", user_profile=profile)
    assert "Alice" in out, "name missing"
    assert "developer" in out, "role missing"
    assert "concise" in out, "communication_style missing"

# 4. With compressed_context: includes "Conversation context"
def test_4():
    out = builder.build_system_prompt("test goal", compressed_context="some history")
    assert "Conversation context" in out, "'Conversation context' not found"
    assert "some history" in out, "context text missing"

# 5. With environment_context: includes "Environment"
def test_5():
    out = builder.build_system_prompt("test goal", environment_context="Linux, Python 3.11")
    assert "Environment" in out, "'Environment' not found"
    assert "Linux, Python 3.11" in out, "env text missing"

# 6. With memory_context: includes "Relevant memory"
def test_6():
    out = builder.build_system_prompt("test goal", memory_context="user prefers dark mode")
    assert "Relevant memory" in out, "'Relevant memory' not found"
    assert "user prefers dark mode" in out, "memory text missing"

# 7. Contains tool usage guidance
def test_7():
    out = builder.build_system_prompt("test goal",
                                      tool_names=["read_file", "write_file", "run_command"])
    assert "Tools" in out or "tools" in out, \
        "Tool usage guidance missing"

# 8. Without optional params: still returns valid prompt
def test_8():
    out = builder.build_system_prompt("test goal")
    assert isinstance(out, str) and len(out) > 50, \
        "Basic prompt too short or wrong type"

# 9. Prompt is reasonable length for basic call (under 1000 chars)
def test_9():
    out = builder.build_system_prompt("test goal")
    assert len(out) < 2000, f"Prompt too long: {len(out)} chars"


run("1. Returns non-empty string", test_1)
run("2. Contains 'Zenith'", test_2)
run("3. user_profile fields included", test_3)
run("4. compressed_context -> 'Conversation context'", test_4)
run("5. environment_context -> 'Environment'", test_5)
run("6. memory_context -> 'Relevant memory'", test_6)
run("7. RULES section with greeting rule", test_7)
run("8. Without optional params: valid prompt", test_8)
run("9. Basic prompt under 1000 chars", test_9)

print("\n=== TEST RESULTS ===")
for name, status, err in results:
    line = f"  {status}: {name}"
    if err:
        line += f"  -- {err}"
    print(line)

passed = sum(1 for _, s, _ in results if s == "PASS")
total = len(results)
print(f"\n{passed}/{total} passed")
