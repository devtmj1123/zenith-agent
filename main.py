#!/usr/bin/env python3
"""Zenith-OS -- Super Agent Operating System"""
from __future__ import annotations
import argparse
import asyncio
import logging
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config.settings import Settings, PROVIDERS
from core.agent_loop import AgentLoop
from core.tools_manager import ToolsManager
from core.memory_compressor import MemoryCompressor
from core.codebook_compiler import CodebookCompiler
from memory.soft_memory import SoftMemory


log = logging.getLogger("zenith")


# --- LLM Client ---

async def llm_call(settings: Settings, messages: list, compressed_context: str = "",
                   use_compressor: bool = False) -> dict:
    """Multi-provider LLM call (OpenAI-compatible API).

    Args:
        use_compressor: If True, route to compressor model (fast local Ollama).
                        If False, use main provider (Groq/NVIDIA/OpenAI).
    """
    import httpx

    if use_compressor:
        base_url = settings.compressor_base_url
        model = settings.compressor_model
        api_key = settings.compressor_api_key
        timeout = 15  # compressor should be fast (local)
    else:
        base_url = settings.llm_base_url
        model = settings.llm_model
        api_key = settings.llm_api_key
        timeout = 60

    system_prompt = "You are Zenith, a proactive AI agent. Use tools to accomplish tasks. Be concise."
    if compressed_context:
        system_prompt += f"\n\nCompressed context: {compressed_context}"

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages[-20:])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": api_messages,
        "max_tokens": 2000,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
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


# --- Agent Builder ---

def build_agent(settings: Settings) -> AgentLoop:
    tools_manager = ToolsManager()
    tools_manager.auto_discover()
    soft_memory = SoftMemory()
    codebook = CodebookCompiler()

    # Main LLM (cloud: Groq/NVIDIA/OpenAI)
    async def _llm_call(messages, compressed_context=""):
        return await llm_call(settings, messages, compressed_context)

    # Compressor LLM (fast local: Ollama llama3.2:3b)
    async def _compress_llm(messages):
        return await llm_call(settings, messages, "", use_compressor=True)

    memory_compressor = MemoryCompressor(
        soft_memory=soft_memory,
        compress_llm_call=_compress_llm,
    )

    return AgentLoop(
        llm_call=_llm_call,
        tools_manager=tools_manager,
        memory_compressor=memory_compressor,
        codebook=codebook,
    )


# --- CLI Commands ---

def cmd_chat(args, settings: Settings):
    """Interactive chat mode."""
    if args.provider:
        settings.resolve_provider(args.provider)

    if not settings.is_configured():
        print(f"\n  Error: No API key for '{settings.provider}'.")
        env_key = PROVIDERS[settings.provider].get("env_key", "ZENITH_API_KEY")
        print(f"  Set {env_key} or use --provider ollama\n")
        sys.exit(1)

    agent = build_agent(settings)

    print()
    print("  +================================================+")
    print("  |  Zenith-OS v1.0 -- Super Agent Operating Sys   |")
    print("  +================================================+")
    print(f"  |  Provider : {settings.provider:<35}|")
    print(f"  |  Model    : {settings.llm_model:<35}|")
    api_status = "set" if settings.llm_api_key else "MISSING"
    print(f"  |  API Key  : {api_status:<35}|")
    print("  +================================================+")
    print("  |  Commands: /quit /clear /provider <name>       |")
    print("  +================================================+")
    print()

    while True:
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd = user_input.split()
            if cmd[0] in ("/quit", "/exit", "/q"):
                break
            if cmd[0] == "/clear":
                print("\033[2J\033[H", end="")
                continue
            if cmd[0] == "/provider":
                if len(cmd) > 1:
                    try:
                        settings.resolve_provider(cmd[1])
                        agent = build_agent(settings)
                        print(f"  Switched to {settings.provider} ({settings.llm_model})")
                    except ValueError as e:
                        print(f"  {e}")
                else:
                    print(f"  Current: {settings.provider} | Available: {', '.join(PROVIDERS.keys())}")
                continue
            if cmd[0] == "/help":
                print("  /quit          -- Exit")
                print("  /clear         -- Clear screen")
                print("  /provider <n>  -- Switch LLM provider")
                print("  /provider      -- Show current provider")
                print("  /help          -- This help")
                continue
            print(f"  Unknown command: {cmd[0]}. Type /help")
            continue

        # Run agent
        result = asyncio.run(agent.run(user_input))
        print(f"\n  Zenith: {result.final_response}\n")


def cmd_check(args, settings: Settings):
    """Health check."""
    if args.provider:
        settings.resolve_provider(args.provider)

    print()
    print("  Zenith-OS Health Check")
    print("  " + "-" * 50)

    # Main provider
    print(f"  [Main LLM]")
    print(f"  Provider      : {settings.provider}")
    print(f"  Model         : {settings.llm_model}")
    print(f"  Base URL      : {settings.llm_base_url}")

    key_status = "set" if settings.llm_api_key else "MISSING"
    env_key = PROVIDERS.get(settings.provider, {}).get("env_key", "ZENITH_API_KEY")
    print(f"  API Key       : {key_status} (set {env_key})")

    # Compressor provider
    print()
    print(f"  [Compressor LLM]")
    print(f"  Provider      : {settings.compressor_provider}")
    print(f"  Model         : {settings.compressor_model}")
    print(f"  Base URL      : {settings.compressor_base_url}")
    c_key_status = "set" if settings.compressor_api_key else "not needed" if settings.compressor_provider == "ollama" else "MISSING"
    print(f"  API Key       : {c_key_status}")

    # Module imports
    checks = [
        ("Physics constants", "memory.hard_memory", "PHYSICS_CONSTANTS"),
        ("Soft memory", "memory.soft_memory", "SoftMemory"),
        ("Zero-error filter", "filters.zero_error_filter", "ZeroErrorFilter"),
        ("Unit standardizer", "filters.unit_standardizer", "UnitStandardizer"),
        ("Entropy brake", "filters.entropy_brake", "EntropyBrake"),
        ("Agent loop", "core.agent_loop", "AgentLoop"),
        ("Failure library", "core.failure_library", "FAILURE_TREE"),
    ]

    print()
    for label, module, attr in checks:
        try:
            mod = __import__(module, fromlist=[attr])
            obj = getattr(mod, attr)
            if hasattr(obj, "__len__"):
                print(f"  {label:<20}: OK ({len(obj)} items)")
            else:
                print(f"  {label:<20}: OK")
        except Exception as e:
            print(f"  {label:<20}: FAIL - {e}")

    # API connectivity test
    print()
    if settings.is_configured():
        print(f"  Testing {settings.provider} connection...", end=" ")
        try:
            import httpx
            resp = httpx.get(
                f"{settings.llm_base_url}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                print("reachable")
            else:
                print(f"HTTP {resp.status_code}")
        except Exception as e:
            print(f"FAIL - {e}")
    else:
        print(f"  Skipping API test (no key)")

    print()


def cmd_server(args, settings: Settings):
    """Start server."""
    if args.provider:
        settings.resolve_provider(args.provider)

    if not settings.is_configured():
        print(f"Error: No API key for '{settings.provider}'")
        sys.exit(1)

    from api.server import ZenithServer
    agent = build_agent(settings)
    server = ZenithServer(agent, host=args.host, port=args.port)
    print(f"\n  Starting Zenith server on {args.host}:{args.port}")
    print(f"  Provider: {settings.provider} ({settings.llm_model})\n")
    asyncio.run(server.start())


def cmd_providers(args, settings: Settings):
    """List available providers."""
    print()
    print("  Available LLM Providers")
    print("  " + "-" * 50)
    for name, preset in PROVIDERS.items():
        env_key = preset.get("env_key") or "none"
        has_key = "OK" if (preset["env_key"] and __import__("os").getenv(preset["env_key"])) else "--"
        marker = " <" if name == settings.provider else ""
        print(f"  {name:<10} {preset['model']:<30} {env_key:<20} [{has_key}]{marker}")
    print()
    print("  Usage: zenith chat --provider groq")
    print("         export GROQ_API_KEY=gsk_...")
    print()


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        prog="zenith",
        description="Zenith-OS -- Super Agent Operating System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  zenith chat                          Start chat (default: groq)
  zenith chat --provider nvidia        Use NVIDIA NIM
  zenith chat --provider ollama        Use local Ollama (no key needed)
  zenith check --provider groq         Test Groq connection
  zenith server --port 9000            Start server on port 9000
  zenith providers                     List all providers
""",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    p_chat = sub.add_parser("chat", help="Interactive chat mode")
    p_chat.add_argument("--provider", "-p", help="LLM provider (openai|groq|nvidia|ollama)")

    p_check = sub.add_parser("check", help="Health check")
    p_check.add_argument("--provider", "-p", help="LLM provider to test")

    p_server = sub.add_parser("server", help="Start WebSocket server")
    p_server.add_argument("--provider", "-p", help="LLM provider")
    p_server.add_argument("--host", default="127.0.0.1", help="Bind host")
    p_server.add_argument("--port", type=int, default=8765, help="Bind port")

    sub.add_parser("providers", help="List available LLM providers")

    args = parser.parse_args()

    settings = Settings()
    settings.load_from_env()

    if args.debug:
        settings.debug = True
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    commands = {
        "chat": cmd_chat,
        "check": cmd_check,
        "server": cmd_server,
        "providers": cmd_providers,
    }

    if args.command in commands:
        commands[args.command](args, settings)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
