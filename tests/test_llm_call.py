"""Tests for main.py llm_call_for_role function.

Uses unittest.mock to patch httpx.AsyncClient so no real API calls are made.
Run: python -m pytest tests/test_llm_call.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
import unittest.mock as mock

import pytest

# Ensure project root on sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config.settings import ModelRole  # noqa: E402
from main import llm_call_for_role  # noqa: E402


def _make_role() -> ModelRole:
    return ModelRole("mimo", "MiMo-v2.5", "test-key", "https://api.xiaomimimo.com/v1")


def _make_mock_response(json_data: dict) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status = mock.MagicMock()
    return resp


def _patch_client(mock_response):
    """Return a context-manager patch for httpx.AsyncClient."""
    patch = mock.patch("httpx.AsyncClient")
    client_cls = patch.start()
    client_cls.return_value.__aenter__.return_value.post = mock.AsyncMock(
        return_value=mock_response
    )
    return patch, client_cls


# ---------------------------------------------------------------------------
# 1. Basic call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_basic_call():
    """Mock returns a normal response. Verify content and tokens_used."""
    role = _make_role()
    messages = [{"role": "user", "content": "Hi"}]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{"message": {"content": "Hello", "role": "assistant"}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, _ = _patch_client(api_response)
    try:
        result = await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    assert result["content"] == "Hello", f"Expected 'Hello', got {result['content']!r}"
    assert result["tokens_used"] == 10, f"Expected 10, got {result['tokens_used']}"
    assert result["prompt_tokens"] == 5
    assert result["completion_tokens"] == 5


# ---------------------------------------------------------------------------
# 2. reasoning_content handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_reasoning_content():
    """When content is empty and reasoning_content exists, content should be merged."""
    role = _make_role()
    messages = [{"role": "user", "content": "Think about it"}]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{
            "message": {
                "content": "",
                "reasoning_content": "I think therefore I am.",
                "role": "assistant",
            }
        }],
        "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
        "model": "MiMo-v2.5",
    })

    patch, _ = _patch_client(api_response)
    try:
        result = await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    assert result["content"] == "I think therefore I am.", (
        f"Expected reasoning merged into content, got {result['content']!r}"
    )
    assert result["reasoning_content"] == "I think therefore I am."


# ---------------------------------------------------------------------------
# 3. Tool calls in response
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_tool_calls():
    """When tool_calls present in message, they should appear in result."""
    role = _make_role()
    messages = [{"role": "user", "content": "What time is it?"}]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{
            "message": {
                "content": "",
                "role": "assistant",
                "tool_calls": [{
                    "id": "tc1",
                    "type": "function",
                    "function": {
                        "name": "get_time",
                        "arguments": "{}",
                    },
                }],
            }
        }],
        "usage": {"total_tokens": 15, "prompt_tokens": 10, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, _ = _patch_client(api_response)
    try:
        result = await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    assert "tool_calls" in result, f"Expected 'tool_calls' key in result, keys={list(result.keys())}"
    assert result["tool_calls"][0]["id"] == "tc1"
    assert result["tool_calls"][0]["function"]["name"] == "get_time"


# ---------------------------------------------------------------------------
# 4. System message dedup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_system_message_dedup():
    """Pass two identical system messages in history; only one should appear in the API payload."""
    role = _make_role()
    sys_content = "You have access to memory."
    messages = [
        {"role": "system", "content": sys_content},
        {"role": "system", "content": sys_content},  # duplicate
        {"role": "user", "content": "Hello"},
    ]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{"message": {"content": "Hi", "role": "assistant"}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, client_cls = _patch_client(api_response)
    try:
        await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    # Grab the payload that was sent to the API
    post_mock = client_cls.return_value.__aenter__.return_value.post
    call_args = post_mock.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")

    system_msgs = [m for m in payload["messages"] if m["role"] == "system"]
    # Should be exactly 2: the injected system_prompt + one deduplicated from messages
    assert len(system_msgs) == 2, (
        f"Expected 2 system messages (prompt + 1 deduped), got {len(system_msgs)}"
    )
    # The deduped content from messages should appear exactly once
    matching = [m for m in system_msgs if m["content"] == sys_content]
    assert len(matching) == 1, (
        f"Expected 1 copy of the user system message, got {len(matching)}"
    )


# ---------------------------------------------------------------------------
# 5. Variable shadowing fix -- ModelRole not overwritten
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_variable_shadowing():
    """Pass a ModelRole as first arg; verify it is not overwritten by message role strings.

    The bug was that a loop variable named 'role' would shadow the function
    parameter 'role', corrupting the ModelRole object.
    """
    role = _make_role()
    original_provider = role.provider
    original_model = role.model
    original_api_key = role.api_key
    original_base_url = role.base_url

    messages = [
        {"role": "system", "content": "sys1"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "again"},
    ]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{"message": {"content": "OK", "role": "assistant"}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, client_cls = _patch_client(api_response)
    try:
        result = await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    # Verify the ModelRole object was NOT mutated
    assert role.provider == original_provider, (
        f"provider changed: {role.provider!r} != {original_provider!r}"
    )
    assert role.model == original_model, (
        f"model changed: {role.model!r} != {original_model!r}"
    )
    assert role.api_key == original_api_key, (
        f"api_key changed: {role.api_key!r} != {original_api_key!r}"
    )
    assert role.base_url == original_base_url, (
        f"base_url changed: {role.base_url!r} != {original_base_url!r}"
    )

    # Also verify the API call used the correct model and auth header
    post_mock = client_cls.return_value.__aenter__.return_value.post
    call_args = post_mock.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")
    headers = call_args.kwargs.get("headers") or call_args[1].get("headers")

    assert payload["model"] == "MiMo-v2.5", (
        f"Payload model wrong: {payload['model']!r}"
    )
    assert "test-key" in headers["Authorization"], (
        f"Auth header wrong: {headers['Authorization']!r}"
    )


# ---------------------------------------------------------------------------
# 6. No tools -- payload should NOT have "tools" key
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_no_tools():
    """Call without tools param. Payload must not contain a 'tools' key."""
    role = _make_role()
    messages = [{"role": "user", "content": "Hello"}]
    system_prompt = "You are a test bot."

    api_response = _make_mock_response({
        "choices": [{"message": {"content": "Hi", "role": "assistant"}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, client_cls = _patch_client(api_response)
    try:
        await llm_call_for_role(role, messages, system_prompt)
    finally:
        patch.stop()

    post_mock = client_cls.return_value.__aenter__.return_value.post
    call_args = post_mock.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")

    assert "tools" not in payload, (
        f"Expected no 'tools' key in payload, but found: {list(payload.keys())}"
    )


# ---------------------------------------------------------------------------
# 7. With tools -- payload SHOULD have "tools" key
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_with_tools():
    """Call with tools param. Payload must contain a 'tools' key with correct value."""
    role = _make_role()
    messages = [{"role": "user", "content": "What time is it?"}]
    system_prompt = "You are a test bot."
    tools = [{
        "type": "function",
        "function": {
            "name": "test",
            "parameters": {},
        },
    }]

    api_response = _make_mock_response({
        "choices": [{"message": {"content": "Hi", "role": "assistant"}}],
        "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        "model": "MiMo-v2.5",
    })

    patch, client_cls = _patch_client(api_response)
    try:
        await llm_call_for_role(role, messages, system_prompt, tools=tools)
    finally:
        patch.stop()

    post_mock = client_cls.return_value.__aenter__.return_value.post
    call_args = post_mock.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")

    assert "tools" in payload, (
        f"Expected 'tools' key in payload, keys={list(payload.keys())}"
    )
    assert payload["tools"] == tools, (
        f"Expected tools={tools}, got {payload['tools']}"
    )
