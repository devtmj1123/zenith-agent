#!/usr/bin/env python3
"""Zenith-OS -- Super Agent Operating System"""
from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import typer
from config.settings import Settings, PROVIDERS
from core.agent_loop import AgentLoop
from core.tools_manager import ToolsManager
from core.memory_compressor import MemoryCompressor
from core.codebook_compiler import CodebookCompiler
from memory.soft_memory import SoftMemory

app = typer.Typer(
    name="zenith",
    help="Zenith-OS -- Super Agent Operating System",
    no_args_is_help=True,
)


# --- LLM Client ---

async def llm_call_for_role(role, messages: list,
                            system_prompt: str = "", max_tokens: int = 2000,
                            tools=None) -> dict:
    """Generic LLM call for any model role."""
    import httpx

    if system_prompt:
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages[-20:])
    else:
        api_messages = messages

    headers = {
        "Authorization": f"Bearer {role.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": role.model,
        "messages": api_messages,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

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
    message = choice["message"]
    usage = data.get("usage", {})

    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""
    if not content.strip() and reasoning.strip():
        content = reasoning

    result = {
        "content": content,
        "reasoning_content": reasoning,
        "tokens_used": usage.get("total_tokens", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "model": data.get("model", role.model),
    }
    if "tool_calls" in message and message["tool_calls"]:
        result["tool_calls"] = message["tool_calls"]

    return result


# --- Agent Builder ---

def build_agent(settings: Settings, on_event=None) -> AgentLoop:
    tools_manager = ToolsManager()

    from tools.builtin import BUILTIN_TOOLS
    for name, fn in BUILTIN_TOOLS.items():
        tools_manager.register(name, fn)

    soft_memory = SoftMemory()
    from tools.builtin.memory_tools import set_soft_memory
    set_soft_memory(soft_memory)
    codebook = CodebookCompiler()

    token_stats = {"prompt": 0, "completion": 0, "total": 0, "model": ""}

    async def _reasoning_call(messages, compressed_context="", tools=None):
        if compressed_context:
            # Inject compressed context as a system message
            messages = [{"role": "system", "content": f"Previous context summary: {compressed_context}"}] + list(messages)
        result = await llm_call_for_role(
            settings.reasoning, messages, tools=tools, max_tokens=8192
        )
        token_stats["prompt"] += result.get("prompt_tokens", 0)
        token_stats["completion"] += result.get("completion_tokens", 0)
        token_stats["total"] += result.get("tokens_used", 0)
        token_stats["model"] = result.get("model", settings.reasoning.model)
        return result

    async def _compression_call(messages):
        sys = "Compress this conversation history into a concise summary. Keep key facts, decisions, and context. Max 200 words."
        return await llm_call_for_role(settings.compression, messages, sys)

    async def _fast_path_call(messages):
        sys = "Answer briefly in 1-2 sentences. Be fast and approximate."
        return await llm_call_for_role(settings.fast_path, messages, sys, max_tokens=200)

    memory_compressor = MemoryCompressor(
        soft_memory=soft_memory,
        compress_llm_call=_compression_call,
    )

    # Initialize Science Research Engine with real clients
    from research.science_engine import ScienceEngine
    from research.sources.pubmed import PubMedClient
    from research.sources.arxiv import ArxivClient
    from memory.hard_memory import PHYSICS_CONSTANTS
    from filters.zero_error_filter import ZeroErrorFilter
    from filters.unit_standardizer import UnitStandardizer
    from tools.builtin import set_science_engine
    import os

    _pubmed = PubMedClient(api_key=os.getenv("PUBMED_API_KEY", ""))
    _arxiv  = ArxivClient()
    _zef    = ZeroErrorFilter()
    _units  = UnitStandardizer()

    science_engine = ScienceEngine(
        llm_client=None,           # wired below after agent build
        arxiv=_arxiv,
        pubmed=_pubmed,
        hard_memory=PHYSICS_CONSTANTS,
        zero_error_filter=_zef,
        unit_standardizer=_units,
    )
    set_science_engine(science_engine)

    agent = AgentLoop(
        llm_call=_reasoning_call,
        tools_manager=tools_manager,
        memory_compressor=memory_compressor,
        codebook=codebook,
        settings=settings,
        on_event=on_event,
    )
    agent._token_stats = token_stats

    # Wire fast-path LLM into dream controller for quick concept matching
    agent.dream_controller.fast_llm_call = _fast_path_call

    # Wire LLM into science engine so hypothesis generation works
    async def _science_llm(prompt: str, max_tokens: int = 300) -> str:
        try:
            result = await _reasoning_call(
                [{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return result.get("content", "")
        except Exception:
            return ""

    science_engine.llm = type("LLMWrapper", (), {
        "complete_raw": staticmethod(_science_llm)
    })()
    science_engine.rebuttal.arxiv  = _arxiv
    science_engine.rebuttal.pubmed = _pubmed

    # Wire debate engine
    from research.debate import SequentialDebate
    agent.debate_engine = SequentialDebate(llm_call=_reasoning_call)

    return agent


# --- Sanitize for Windows console ---

def _sanitize_print(text: str) -> str:
    """Remove emoji and special chars that break Windows cp1252."""
    import re
    return re.sub(r'[\U00010000-\U0010ffff☀-➿⭐❤✔✖❌❎➕➖➗✅✨⭐❗❕❓❔‼⁉〰〽ℹ⤴⤵▪▫▶◀◻◼◽◾⬅⬆⬇⬛⬜⏩⏪⏫⏬⏭⏮⏯⏰⏱⏲⏳⏸⏹⏺⏏‍⃣️⚕⚔⚖⚗⚙♻☢☣☦☪☮☯☸♀♂♈-♓♟♠♣♥♦♨♰♱♾⚒⚓⚠⚡⚪⚫⚰⚱⚽⚾⛄⛅⛈⛎⛏⛑⛓⛔⛩⛪⛰-⛵⛷-⛺⛽✂✅✈-✍✏✒✔✖✝✡✨✳✴❄❇❌❎❓-❕❗❣❤❥❮❯➕-➗➡➰➿⤴⤵⬅-⬇⬛⬜⭐⭕〰〽㊗㊙]', '', text)


# --- CLI Commands ---

@app.command()
def chat(
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider (openai|groq|nvidia|ollama|mimo)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Interactive chat mode."""
    settings = Settings()
    settings.load_from_env()

    if provider:
        try:
            settings.resolve_provider(provider)
        except ValueError as e:
            print(f"  \033[31m{e}\033[0m")
            raise typer.Exit(1)

    if debug:
        settings.debug = True
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if not settings.is_configured():
        env_key = PROVIDERS.get(settings.reasoning.provider, {}).get("env_key", "REASONING_API_KEY")
        print(f"\n  Error: No API key for '{settings.reasoning.provider}'.")
        print(f"  Set {env_key} or use --provider ollama\n")
        raise typer.Exit(1)

    # --- Event handler for streaming agent events ---
    from core.types import EventType

    def _on_event(event):
        safe = _sanitize_print(event.content)
        if event.type == EventType.THINKING:
            print(f"  \033[90m[Thinking] {safe}\033[0m")
        elif event.type == EventType.ACTION:
            print(f"  \033[36m[Tool] {safe}\033[0m")
        elif event.type == EventType.OBSERVATION:
            # Truncate long observations
            if len(safe) > 200:
                safe = safe[:200] + "..."
            print(f"  \033[33m[Result] {safe}\033[0m")
        elif event.type == EventType.RESPONSE:
            # Narration / mid-task text
            if safe.strip():
                print(f"  \033[35m[Narrator] {safe}\033[0m")
        elif event.type == EventType.ERROR:
            print(f"  \033[31m[Error] {safe}\033[0m")
        elif event.type == EventType.PERMISSION:
            print(f"  \033[93m[Permission] {safe}\033[0m")
        elif event.type == EventType.COMPRESSED:
            print(f"  \033[90m[Compressed] {safe}\033[0m")

    agent = build_agent(settings, on_event=_on_event)

    # Preload embedding model
    import warnings
    warnings.filterwarnings("ignore", message=".*HF Hub.*")
    if SoftMemory._embedding_model is None:
        print("  Loading embedding model...", end=" ", flush=True)
        try:
            from sentence_transformers import SentenceTransformer
            SoftMemory._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("done")
        except Exception:
            print("skipped (not installed)")

    def _short_model(name: str) -> str:
        return name.split("/")[-1] if "/" in name else name

    # --- Header ---
    print()
    print("  \033[1;36mZenith-OS\033[0m v1.0  --  Super Agent Operating System")
    print("  " + "\033[90m" + "-" * 52 + "\033[0m")
    print(f"  \033[1mReasoning\033[0m    {settings.reasoning.provider}/{_short_model(settings.reasoning.model)}")
    print(f"  \033[1mCompression\033[0m  {settings.compression.provider}/{_short_model(settings.compression.model)}")
    print(f"  \033[1mFast Path\033[0m    {settings.fast_path.provider}/{_short_model(settings.fast_path.model)}")
    print(f"  \033[1mTools\033[0m        {len(agent.tools.list_tools())} registered")
    print("  " + "\033[90m" + "-" * 52 + "\033[0m")
    print("  Type \033[1m/help\033[0m for commands, \033[1m/quit\033[0m to exit")
    print()

    # --- Proactive memory recall ---
    try:
        from core.intent_tracker import IntentTracker
        tracker = IntentTracker()
        resume = tracker.get_resume_prompt()
        if resume:
            print(f"  \033[93m[Memory]\033[0m {_sanitize_print(resume)}")
            print()
    except Exception:
        pass

    # Check soft memory count
    db_path = agent.memory.soft.DB_PATH
    if db_path.exists():
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
            mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if mem_count > 0:
            print(f"  \033[90m[{mem_count} memories loaded]\033[0m")
            print()

    # --- TTS state ---
    tts_enabled = False
    tts_voice = "female"
    dual_channel = None

    def _init_tts():
        nonlocal dual_channel
        if dual_channel is None:
            from tts.zenith_tts import ZenithTTS
            from core.dual_channel import DualChannel
            tts = ZenithTTS(voice=tts_voice)
            dual_channel = DualChannel(tts_engine=tts)
        return dual_channel

    async def _speak(text: str):
        if not tts_enabled:
            return
        try:
            dc = _init_tts()
            await dc.speak(text)
        except Exception as e:
            print(f"  \033[90mTTS error: {e}\033[0m")

    # --- Tab completion ---
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.styles import Style
        from prompt_toolkit.formatted_text import HTML

        slash_commands = [
            "/quit", "/exit", "/q", "/clear", "/help",
            "/provider", "/models", "/memory", "/tools",
            "/tts", "/voice", "/speak",
        ]
        provider_names = list(PROVIDERS.keys())
        voice_names = ["female", "male", "female_zh", "male_zh"]
        all_completions = (
            slash_commands
            + [f"/provider {p}" for p in provider_names]
            + [f"/voice {v}" for v in voice_names]
            + ["/tts on", "/tts off"]
        )

        completer = WordCompleter(all_completions, ignore_case=True)
        style = Style.from_dict({"prompt": "bold green"})
        session = PromptSession(style=style)
        _has_prompt_toolkit = True
    except ImportError:
        _has_prompt_toolkit = False

    # --- Main loop ---
    while True:
        try:
            if _has_prompt_toolkit:
                user_input = session.prompt(
                    HTML("<prompt>  You</prompt>: "),
                    completer=completer,
                ).strip()
            else:
                user_input = input("  \033[1;32mYou\033[0m: ").strip()
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
                        agent = build_agent(settings, on_event=_on_event)
                        print(f"  Switched to \033[1m{settings.reasoning.provider}/{_short_model(settings.reasoning.model)}\033[0m")
                    except ValueError as e:
                        print(f"  \033[31m{e}\033[0m")
                else:
                    print(f"  Reasoning: {settings.reasoning.provider} | Available: {', '.join(PROVIDERS.keys())}")
                continue
            if cmd[0] == "/help":
                print("  \033[1mCommands:\033[0m")
                print("    /quit          Exit")
                print("    /clear         Clear screen")
                print("    /provider <n>  Switch reasoning provider")
                print("    /provider      Show current provider")
                print("    /models        Show all 3 model roles")
                print("    /memory        Show memory stats")
                print("    /tools         List registered tools")
                print("    /tts on|off    Toggle text-to-speech")
                print("    /voice <name>  Change TTS voice (female/male/female_zh/male_zh)")
                print("    /speak <text>  Speak text aloud")
                print("    /help          This help")
                continue
            if cmd[0] == "/models":
                print(f"  Reasoning   : \033[1m{settings.reasoning.provider}/{settings.reasoning.model}\033[0m")
                print(f"  Compression : \033[1m{settings.compression.provider}/{settings.compression.model}\033[0m")
                print(f"  Fast Path   : \033[1m{settings.fast_path.provider}/{settings.fast_path.model}\033[0m")
                continue
            if cmd[0] == "/memory":
                if db_path.exists():
                    import sqlite3
                    with sqlite3.connect(str(db_path)) as conn:
                        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                    print(f"  Soft memory: \033[1m{count}\033[0m memories ({db_path})")
                else:
                    print(f"  Soft memory: empty")
                trace = agent.memory.get_recall_trace()
                if trace:
                    print(f"  Last recall: {len(trace)} memories queried")
                continue
            if cmd[0] == "/tools":
                for t in agent.tools.list_tools():
                    print(f"  \033[36m{t}\033[0m")
                continue
            if cmd[0] == "/tts":
                if len(cmd) > 1 and cmd[1].lower() in ("on", "off"):
                    tts_enabled = cmd[1].lower() == "on"
                    print(f"  TTS: \033[1m{'ON' if tts_enabled else 'OFF'}\033[0m")
                elif len(cmd) > 1 and cmd[1].lower() == "status":
                    print(f"  TTS: \033[1m{'ON' if tts_enabled else 'OFF'}\033[0m | Voice: {tts_voice}")
                else:
                    print(f"  Usage: /tts on|off|status")
                continue
            if cmd[0] == "/voice":
                if len(cmd) > 1:
                    new_voice = cmd[1].lower()
                    valid_voices = ["female", "male", "female_zh", "male_zh"]
                    if new_voice in valid_voices:
                        tts_voice = new_voice
                        dual_channel = None  # Reset to pick up new voice
                        print(f"  Voice: \033[1m{tts_voice}\033[0m")
                    else:
                        print(f"  Valid voices: {', '.join(valid_voices)}")
                else:
                    print(f"  Current voice: \033[1m{tts_voice}\033[0m")
                    print(f"  Available: female, male, female_zh, male_zh")
                continue
            if cmd[0] == "/speak":
                if len(cmd) > 1:
                    text = " ".join(cmd[1:])
                    asyncio.run(_speak(text))
                else:
                    print(f"  Usage: /speak <text>")
                continue
            print(f"  Unknown: {cmd[0]}. Type /help")
            continue

        # --- Run agent ---
        result = asyncio.run(agent.run(user_input))

        # Response
        safe_response = _sanitize_print(result.final_response)
        print(f"\n  \033[1;35mZenith\033[0m: {safe_response}")

        # Auto-speak if TTS enabled
        if tts_enabled and result.final_response:
            asyncio.run(_speak(result.final_response))

        # Stats line
        ts = agent._token_stats
        model_display = _short_model(ts.get("model", settings.reasoning.model))
        stats = []
        if ts["prompt"] > 0:
            stats.append(f"\033[32min={ts['prompt']}\033[0m")
            stats.append(f"\033[31mout={ts['completion']}\033[0m")
        if result.tool_calls_made > 0:
            stats.append(f"\033[36mtools={result.tool_calls_made}\033[0m")
        if result.iteration > 1:
            stats.append(f"iter={result.iteration}")
        stats.append(f"\033[90m{settings.reasoning.provider}/{model_display}\033[0m")
        print(f"  [{'  '.join(stats)}]")
        ts["prompt"] = ts["completion"] = ts["total"] = 0
        print()


@app.command()
def check(
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider to test"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Health check."""
    settings = Settings()
    settings.load_from_env()

    if provider:
        try:
            settings.resolve_provider(provider)
        except ValueError as e:
            print(f"  \033[31m{e}\033[0m")
            raise typer.Exit(1)

    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    print()
    print("  Zenith-OS Health Check")
    print("  " + "-" * 55)

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

    checks = [
        ("Soft memory", "memory.soft_memory", "SoftMemory"),
        ("Agent loop", "core.agent_loop", "AgentLoop"),
        ("Tools manager", "core.tools_manager", "ToolsManager"),
        ("Codebook", "core.codebook_compiler", "CodebookCompiler"),
        ("Flow regulator", "core.flow_regulator", "FlowRegulator"),
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


@app.command()
def server(
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8765, "--port", help="Bind port"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Start WebSocket server."""
    settings = Settings()
    settings.load_from_env()

    if provider:
        try:
            settings.resolve_provider(provider)
        except ValueError as e:
            print(f"  \033[31m{e}\033[0m")
            raise typer.Exit(1)

    if debug:
        settings.debug = True
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if not settings.is_configured():
        print(f"Error: No API key for '{settings.reasoning.provider}'")
        raise typer.Exit(1)

    from api.server import ZenithServer
    agent = build_agent(settings)
    server = ZenithServer(agent, host=host, port=port)
    print(f"\n  Starting Zenith server on {host}:{port}")
    print(f"  Reasoning: {settings.reasoning.provider}/{settings.reasoning.model}")
    print(f"  Compression: {settings.compression.provider}/{settings.compression.model}\n")
    asyncio.run(server.start())


@app.command(name="providers")
def list_providers(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """List available LLM providers and current model roles."""
    import os
    settings = Settings()
    settings.load_from_env()

    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

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


def main():
    app()

if __name__ == "__main__":
    main()
