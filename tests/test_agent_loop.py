"""Integration tests for core/agent_loop.py with mock LLM calls.

No real API keys needed. Uses lightweight mock stubs for SoftMemory,
MemoryCompressor, and CodebookCompiler.
"""
import asyncio
import sys
import os
import types

# ── Add project root to path ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Lightweight mock stubs ────────────────────────────────────────────
# These replace heavy dependencies (SQLite, YAML, TTS) so the tests
# can run without any external resources.

from core.types import ToolResult


class MockSoftMemory:
    """Minimal SoftMemory stand-in for testing."""

    def __init__(self):
        self._stored = []

    async def recall(self, query: str, top_k: int = 5):
        return []

    async def write(self, content: str, session_id: str = "",
                    layer: str = "episodic", confidence: float = 0.8):
        self._stored.append(content)


class MockMemoryCompressor:
    """Lightweight MemoryCompressor that avoids SoftMemory's SQLite."""

    def __init__(self, soft_memory=None):
        self.soft = soft_memory or MockSoftMemory()
        self._recall_trace = []
        self._compress_llm = None

    async def recall_with_trace(self, query: str, top_k: int = 5):
        return []

    async def compress_history(self, messages, max_tokens=2000):
        return ""

    async def store_interaction(self, user_msg, assistant_msg, session_id="",
                                tool_calls_made=0, last_tool_token=""):
        pass


class MockCodebookCompiler:
    """Empty codebook — no tools defined, just the interface."""

    def get_tools_schema(self):
        return []

    def get_risk_levels(self):
        return {}


# ── Patch heavy modules before importing AgentLoop ────────────────────
# We replace the real constructors with our lightweight mocks so
# AgentLoop.__init__ doesn't try to load YAML, create SQLite DBs,
# or initialise TTS engines.

from core import memory_compressor as _mc_mod
from core import codebook_compiler as _cb_mod

_original_mc_init = _mc_mod.MemoryCompressor.__init__
_original_cb_init = _cb_mod.CodebookCompiler.__init__

_mc_mod.MemoryCompressor.__init__ = lambda self, **kw: None
_cb_mod.CodebookCompiler.__init__ = lambda self, **kw: None

# Now safe to import AgentLoop — its __init__ will use the patched stubs
from core.agent_loop import AgentLoop

# Restore originals (we won't need them, but good hygiene)
_mc_mod.MemoryCompressor.__init__ = _original_mc_init
_cb_mod.CodebookCompiler.__init__ = _original_cb_init


# ── Helpers ───────────────────────────────────────────────────────────

def make_tools_manager():
    """Create a ToolsManager with a mock get_time tool registered."""
    from core.tools_manager import ToolsManager
    tm = ToolsManager()

    async def mock_get_time(params):
        return {"success": True, "data": {"time": "21:00"}}

    tm.register("get_time", mock_get_time)
    return tm


def build_agent(llm_call):
    """Build an AgentLoop wired to the given mock LLM callable."""
    tools = make_tools_manager()
    mem = MockMemoryCompressor()
    cb = MockCodebookCompiler()
    return AgentLoop(
        llm_call=llm_call,
        tools_manager=tools,
        memory_compressor=mem,
        codebook=cb,
    )


def run_sync(coro):
    """Run an async coroutine from synchronous test code."""
    return asyncio.run(coro)


# ── Test cases ────────────────────────────────────────────────────────

def test_simple_greeting():
    """Mock LLM returns a plain greeting with no tool calls."""
    responses = [{"content": "Hello!", "tokens_used": 10}]

    async def mock_llm(messages, compressed="", tools=None):
        return responses.pop(0)

    agent = build_agent(mock_llm)
    state = run_sync(agent.run("hi"))

    ok = True
    if state.final_response != "Hello!":
        print(f"  FAIL final_response: expected 'Hello!', got '{state.final_response}'")
        ok = False
    if state.tool_calls_made != 0:
        print(f"  FAIL tool_calls_made: expected 0, got {state.tool_calls_made}")
        ok = False
    if state.iteration != 1:
        print(f"  FAIL iteration: expected 1, got {state.iteration}")
        ok = False
    if ok:
        print("  PASS")
    return ok


def test_tool_call_then_response():
    """First LLM call returns a tool_calls, second call returns final text."""
    responses = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "get_time",
                        "arguments": "{}",
                    },
                    "type": "function",
                }
            ],
            "tokens_used": 50,
        },
        {"content": "It's 9 PM", "tokens_used": 20},
    ]

    async def mock_llm(messages, compressed="", tools=None):
        return responses.pop(0)

    agent = build_agent(mock_llm)
    state = run_sync(agent.run("What time is it?"))

    ok = True
    if state.final_response != "It's 9 PM":
        print(f"  FAIL final_response: expected 'It's 9 PM', got '{state.final_response}'")
        ok = False
    if state.tool_calls_made != 1:
        print(f"  FAIL tool_calls_made: expected 1, got {state.tool_calls_made}")
        ok = False
    if state.iteration != 2:
        print(f"  FAIL iteration: expected 2, got {state.iteration}")
        ok = False
    if ok:
        print("  PASS")
    return ok


def test_empty_response_retry():
    """First call (with tools) returns empty content; retry without tools succeeds."""
    call_log = []

    async def mock_llm(messages, compressed="", tools=None):
        call_log.append({"tools": tools})
        if len(call_log) == 1:
            # First call (with tools) — empty response, no tool_calls
            return {"content": "", "tokens_used": 10}
        else:
            # Retry (without tools) — real answer
            return {"content": "Hi there", "tokens_used": 10}

    agent = build_agent(mock_llm)
    state = run_sync(agent.run("hello"))

    ok = True
    if state.final_response != "Hi there":
        print(f"  FAIL final_response: expected 'Hi there', got '{state.final_response}'")
        ok = False
    # Verify the first call had tools, the retry had tools=None
    if len(call_log) != 2:
        print(f"  FAIL expected 2 LLM calls, got {len(call_log)}")
        ok = False
    else:
        if call_log[0]["tools"] is None:
            print("  FAIL first call should have had tools schema")
            ok = False
        if call_log[1]["tools"] is not None:
            print("  FAIL retry call should have had tools=None")
            ok = False
    if ok:
        print("  PASS")
    return ok


def test_reasoning_content_fallback():
    """LLM returns empty content but non-empty reasoning_content."""
    responses = [
        {"content": "", "reasoning_content": "The answer is 42", "tokens_used": 10},
    ]

    async def mock_llm(messages, compressed="", tools=None):
        return responses.pop(0)

    agent = build_agent(mock_llm)
    state = run_sync(agent.run("what is the meaning of life?"))

    ok = True
    if state.final_response != "The answer is 42":
        print(f"  FAIL final_response: expected 'The answer is 42', got '{state.final_response}'")
        ok = False
    if ok:
        print("  PASS")
    return ok


# ── Runner ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("1. Simple greeting (no tools)", test_simple_greeting),
        ("2. Tool call then response",    test_tool_call_then_response),
        ("3. Empty response retry",       test_empty_response_retry),
        ("4. reasoning_content fallback",  test_reasoning_content_fallback),
    ]

    print("=" * 60)
    print("AgentLoop integration tests (mock LLM)")
    print("=" * 60)

    results = []
    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            passed = fn()
        except Exception as exc:
            print(f"  FAIL (exception): {exc}")
            import traceback
            traceback.print_exc()
            passed = False
        results.append((name, passed))

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{total} tests passed")
    print("=" * 60)

    sys.exit(0 if passed_count == total else 1)
