#!/usr/bin/env python3
"""Zenith-OS — Super Agent Operating System"""
from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path (for `pip install -e .` and `zenith` CLI)
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config.settings import Settings
from core.agent_loop import AgentLoop
from core.tools_manager import ToolsManager
from core.memory_compressor import MemoryCompressor
from core.codebook_compiler import CodebookCompiler
from memory.soft_memory import SoftMemory


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("zenith")


def build_agent(settings: Settings) -> AgentLoop:
    """Build the agent with all components."""
    tools_manager = ToolsManager()
    tools_manager.auto_discover()

    soft_memory = SoftMemory()
    memory_compressor = MemoryCompressor(soft_memory)
    codebook = CodebookCompiler()

    async def llm_call(messages, compressed_context=""):
        """LLM API call."""
        import httpx

        system_prompt = "You are Zenith, a proactive AI agent. Use tools to accomplish tasks."
        if compressed_context:
            system_prompt += f"\n\nCompressed context: {compressed_context}"

        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages[-20:])  # Keep last 20 messages

        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "messages": api_messages,
            "max_tokens": 2000,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"]["content"],
            "tokens_used": usage.get("total_tokens", 0),
        }

    agent = AgentLoop(
        llm_call=llm_call,
        tools_manager=tools_manager,
        memory_compressor=memory_compressor,
        codebook=codebook,
    )

    return agent


async def chat_mode(settings: Settings):
    """Interactive chat mode."""
    agent = build_agent(settings)
    print("\n  Zenith-OS v1.0 — Super Agent Operating System")
    print("  Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        result = await agent.run(user_input)
        print(f"\nZenith: {result.final_response}\n")


async def server_mode(settings: Settings):
    """Start WebSocket + HTTP server."""
    from api.server import ZenithServer

    agent = build_agent(settings)
    server = ZenithServer(agent)
    log.info("Starting Zenith server on %s:%s", server.host, server.port)
    await server.start()


def main():
    settings = Settings()
    settings.load_from_env()

    mode = "chat"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "server":
        asyncio.run(server_mode(settings))
    elif mode == "chat":
        asyncio.run(chat_mode(settings))
    elif mode == "check":
        print("Zenith-OS health check:")
        print(f"  LLM model: {settings.llm_model}")
        print(f"  API key set: {'yes' if settings.llm_api_key else 'NO'}")
        print(f"  Token budget: {settings.token_budget}")
        # Test imports
        try:
            from memory.hard_memory import PHYSICS_CONSTANTS
            print(f"  Physics constants: {len(PHYSICS_CONSTANTS)} loaded")
        except Exception as e:
            print(f"  Physics constants: FAILED - {e}")
        try:
            from memory.soft_memory import SoftMemory
            sm = SoftMemory()
            print(f"  Soft memory: OK (DB at {sm.DB_PATH})")
        except Exception as e:
            print(f"  Soft memory: FAILED - {e}")
        print("  All checks passed!")
    else:
        print(f"Usage: python main.py [chat|server|check]")


if __name__ == "__main__":
    main()
