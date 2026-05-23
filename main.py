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

async def llm_call_for_role(role: "ModelRole", messages: list,
                            system_prompt: str = "", max_tokens: int = 2000) -> dict:
    """Generic LLM call for any model role."""
    import httpx

    if not system_prompt:
        system_prompt = "You are Zenith, a proactive AI agent. Be concise."

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages[-20:])

    headers = {
        "Authorization": f"Bearer {role.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": role.model,
        "messages": api_messages,
        "max_tokens": max_tokens,
    }

    timeout = 15 if role.provider == "ollama" else 60

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{role.base_url}/chat/completions",
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
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "model": data.get("model", role.model),
    }


# --- Agent Builder ---

def build_agent(settings: Settings) -> AgentLoop:
    tools_manager = ToolsManager()

    # Register builtin tools
    from tools.builtin import BUILTIN_TOOLS
    for name, fn in BUILTIN_TOOLS.items():
        tools_manager.register(name, fn)

    soft_memory = SoftMemory()
    codebook = CodebookCompiler()

    # Token tracking (mutable container shared across calls)
    token_stats = {"prompt": 0, "completion": 0, "total": 0, "model": ""}

    # REASONING model — main thinking + tool calls
    async def _reasoning_call(messages, compressed_context=""):
        sys = "You are Zenith, a proactive AI agent. Use tools to accomplish tasks. Be concise."
        if compressed_context:
            sys += f"\n\nCompressed context: {compressed_context}"
        result = await llm_call_for_role(settings.reasoning, messages, sys)
        token_stats["prompt"] += result.get("prompt_tokens", 0)
        token_stats["completion"] += result.get("completion_tokens", 0)
        token_stats["total"] += result.get("tokens_used", 0)
        token_stats["model"] = result.get("model", settings.reasoning.model)
        return result

    # COMPRESSION model — summarize history
    async def _compression_call(messages):
        sys = "Compress this conversation history into a concise summary. Keep key facts, decisions, and context. Max 200 words."
        return await llm_call_for_role(settings.compression, messages, sys)

    # FAST PATH model — quick approximate answers
    async def _fast_path_call(messages):
        sys = "Answer briefly in 1-2 sentences. Be fast and approximate."
        return await llm_call_for_role(settings.fast_path, messages, sys, max_tokens=200)

    memory_compressor = MemoryCompressor(
        soft_memory=soft_memory,
        compress_llm_call=_compression_call,
    )

    agent = AgentLoop(
        llm_call=_reasoning_call,
        tools_manager=tools_manager,
        memory_compressor=memory_compressor,
        codebook=codebook,
    )
    agent._token_stats = token_stats  # Attach for CLI display
    return agent


# --- CLI Commands ---

def cmd_chat(args, settings: Settings):
    """Interactive chat mode."""
    if args.provider:
        settings.resolve_provider(args.provider)

    if not settings.is_configured():
        print(f"\n  Error: No API key for '{settings.reasoning.provider}'.")
        env_key = PROVIDERS.get(settings.reasoning.provider, {}).get("env_key", "REASONING_API_KEY")
        print(f"  Set {env_key} or use --provider ollama\n")
        sys.exit(1)

    agent = build_agent(settings)

    # Preload embedding model so first message isn't slow
    import warnings
    warnings.filterwarnings("ignore", message=".*HF Hub.*")
    from memory.soft_memory import SoftMemory
    if SoftMemory._embedding_model is None:
        print("  Loading embedding model...", end=" ", flush=True)
        from sentence_transformers import SentenceTransformer
        SoftMemory._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("done")

    def _short_model(name: str) -> str:
        """Shorten model name for display."""
        return name.split("/")[-1] if "/" in name else name

    print()
    print("  +====================================================+")
    print("  |  Zenith-OS v1.0 -- Super Agent Operating System    |")
    print("  +====================================================+")
    print(f"  |  Reasoning   : {settings.reasoning.provider}/{_short_model(settings.reasoning.model):<28}|")
    print(f"  |  Compression : {settings.compression.provider}/{_short_model(settings.compression.model):<28}|")
    print(f"  |  Fast Path   : {settings.fast_path.provider}/{_short_model(settings.fast_path.model):<28}|")
    print("  +====================================================+")
    print("  |  Commands: /quit /clear /provider <name> /history  |")
    print("  +====================================================+")
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
                        print(f"  Switched reasoning to {settings.reasoning.provider}/{settings.reasoning.model}")
                    except ValueError as e:
                        print(f"  {e}")
                else:
                    print(f"  Reasoning: {settings.reasoning.provider} | Available: {', '.join(PROVIDERS.keys())}")
                continue
            if cmd[0] == "/help":
                print("  /quit          -- Exit")
                print("  /clear         -- Clear screen")
                print("  /provider <n>  -- Switch reasoning provider")
                print("  /provider      -- Show current provider")
                print("  /models        -- Show all 3 model roles")
                print("  /memory        -- Show memory stats")
                print("  /help          -- This help")
                continue
            if cmd[0] == "/models":
                print(f"  Reasoning   : {settings.reasoning.provider}/{settings.reasoning.model}")
                print(f"  Compression : {settings.compression.provider}/{settings.compression.model}")
                print(f"  Fast Path   : {settings.fast_path.provider}/{settings.fast_path.model}")
                continue
            if cmd[0] == "/memory":
                db_path = agent.memory.soft.DB_PATH
                if db_path.exists():
                    import sqlite3
                    with sqlite3.connect(str(db_path)) as conn:
                        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                    print(f"  Soft memory: {count} memories stored ({db_path})")
                else:
                    print(f"  Soft memory: empty (no memories yet)")
                continue
            print(f"  Unknown command: {cmd[0]}. Type /help")
            continue

        # Run agent
        result = asyncio.run(agent.run(user_input))

        # Response
        print(f"\n  Zenith: {result.final_response}")

        # Stats line: tokens in/out, model, tools
        ts = agent._token_stats
        model_display = _short_model(ts.get("model", settings.reasoning.model))
        stats_parts = [f"model={settings.reasoning.provider}/{model_display}"]
        if ts["prompt"] > 0:
            stats_parts.append(f"in={ts['prompt']}")
            stats_parts.append(f"out={ts['completion']}")
        if result.tool_calls_made > 0:
            stats_parts.append(f"tools={result.tool_calls_made}")
        if result.iteration > 1:
            stats_parts.append(f"iter={result.iteration}")
        print(f"  [{', '.join(stats_parts)}]")
        # Reset for next turn
        ts["prompt"] = ts["completion"] = ts["total"] = 0
        print()


def cmd_check(args, settings: Settings):
    """Health check."""
    if args.provider:
        settings.resolve_provider(args.provider)

    print()
    print("  Zenith-OS Health Check")
    print("  " + "-" * 55)

    # All 3 model roles
    for label, role in [
        ("REASONING", settings.reasoning),
        ("COMPRESSION", settings.compression),
        ("FAST PATH", settings.fast_path),
    ]:
        key_status = "set" if role.api_key else ("no key needed" if role.provider == "ollama" else "MISSING")
        print(f"  [{label}]")
        print(f"    Provider : {role.provider}")
        print(f"    Model    : {role.model}")
        print(f"    API Key  : {key_status}")
        print()

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

    # API connectivity test (reasoning provider only)
    print()
    if settings.reasoning.is_configured():
        print(f"  Testing {settings.reasoning.provider} connection...", end=" ")
        try:
            import httpx
            resp = httpx.get(
                f"{settings.reasoning.base_url}/models",
                headers={"Authorization": f"Bearer {settings.reasoning.api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                print("reachable")
            else:
                print(f"HTTP {resp.status_code}")
        except Exception as e:
            print(f"FAIL - {e}")
    else:
        print(f"  Skipping API test (no reasoning key)")

    print()


def cmd_server(args, settings: Settings):
    """Start server."""
    if args.provider:
        settings.resolve_provider(args.provider)

    if not settings.is_configured():
        print(f"Error: No API key for '{settings.reasoning.provider}'")
        sys.exit(1)

    from api.server import ZenithServer
    agent = build_agent(settings)
    server = ZenithServer(agent, host=args.host, port=args.port)
    print(f"\n  Starting Zenith server on {args.host}:{args.port}")
    print(f"  Reasoning: {settings.reasoning.provider}/{settings.reasoning.model}")
    print(f"  Compression: {settings.compression.provider}/{settings.compression.model}\n")
    asyncio.run(server.start())


def cmd_providers(args, settings: Settings):
    """List available providers and current model roles."""
    import os
    print()
    print("  Available LLM Providers")
    print("  " + "-" * 55)
    for name, preset in PROVIDERS.items():
        env_key = preset.get("env_key") or "none"
        has_key = "OK" if (preset["env_key"] and os.getenv(preset["env_key"])) else "--"
        print(f"  {name:<10} {preset['model']:<30} {env_key:<20} [{has_key}]")
    print()
    print("  Current Model Roles (.env)")
    print("  " + "-" * 55)
    for label, role in [
        ("REASONING", settings.reasoning),
        ("COMPRESSION", settings.compression),
        ("FAST PATH", settings.fast_path),
    ]:
        print(f"  {label:<12} {role.provider}/{role.model}")
    print()
    print("  Usage: zenith chat --provider groq")
    print("         Set REASONING_PROVIDER, COMPRESSION_PROVIDER, FAST_PATH_PROVIDER in .env")
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
