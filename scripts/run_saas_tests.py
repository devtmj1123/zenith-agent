"""SaaS coding test runner — runs queries through Zenith and scores results.

Usage:
  python scripts/run_saas_tests.py              # Run all tests
  python scripts/run_saas_tests.py --tier T1    # Run specific tier
  python scripts/run_saas_tests.py --query 0    # Run specific query by index

Scoring:
  - Intent (0-30): Did the agent understand the task?
  - Efficiency (0-30): Token usage, tool calls, time
  - Quality (0-40): Code correctness, completeness, no errors
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root and scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from test_saas_coding import TEST_QUERIES, SCORING


def score_result(query: dict, result, elapsed: float) -> dict:
    """Score an agent result against expected outputs."""
    expect = set(query["expect"])
    max_time = query["max_time"]
    tier = query["tier"]

    # Intent score (0-30): did it understand the task?
    # Check if final_response mentions key concepts
    response = (result.final_response or "").lower()
    intent_matches = sum(1 for e in expect if e.lower() in response)
    intent_score = min(30, int(intent_matches / len(expect) * 30))

    # Efficiency score (0-30): token usage and time
    tokens = result.tokens_used or (result.input_tokens + result.output_tokens)
    tool_calls = result.tool_calls_made

    # Token efficiency: <10k=30, <30k=20, <60k=10, else 5
    if tokens < 10000:
        token_score = 30
    elif tokens < 30000:
        token_score = 20
    elif tokens < 60000:
        token_score = 10
    else:
        token_score = 5

    # Time efficiency: under max_time=full, 2x=max/2, etc.
    time_ratio = max_time / max(elapsed, 1)
    time_score = min(15, int(time_ratio * 15))

    # Tool efficiency: <10 calls=full, <20=half
    if tool_calls < 10:
        tool_score = 15
    elif tool_calls < 20:
        tool_score = 8
    else:
        tool_score = 3

    efficiency_score = token_score + min(tool_score, 15)

    # Quality score (0-40): did it produce working code?
    # Check for files created, no errors, key patterns
    quality_score = 0

    # Check if it actually did something (not just responded)
    if result.tool_calls_made > 0:
        quality_score += 10

    # Check for expected patterns in response
    for e in expect:
        if e.lower() in response:
            quality_score += 5

    quality_score = min(40, quality_score)

    total = intent_score + efficiency_score + quality_score
    grade = (
        "A" if total >= 80 else
        "B" if total >= 65 else
        "C" if total >= 50 else
        "D" if total >= 35 else
        "F"
    )

    return {
        "total": total,
        "grade": grade,
        "intent": intent_score,
        "efficiency": efficiency_score,
        "quality": quality_score,
        "tokens": tokens,
        "tool_calls": tool_calls,
        "elapsed": round(elapsed, 1),
        "response_preview": (result.final_response or "")[:200],
    }


def _sanitize_print(text: str) -> str:
    """Remove characters that can't be encoded in the console."""
    return text.encode("ascii", errors="replace").decode("ascii")


def print_result(idx: int, query: dict, score: dict):
    """Print a single test result."""
    tier = query["tier"]
    print(f"\n{'='*60}")
    print(f"  [{idx}] {tier}: {query['query'][:70]}...")
    print(f"  {'='*60}")
    print(f"  Score: {score['total']}/100 {score['grade']}")
    print(f"  +-- Intent: {score['intent']}/30  Eff: {score['efficiency']}/30  Quality: {score['quality']}/40")
    print(f"  +-- Tokens: {score['tokens']:,}  Tools: {score['tool_calls']}  Time: {score['elapsed']}s")
    print(f"  +-- Response: {_sanitize_print(score['response_preview'][:100])}...")


def print_summary(results: list):
    """Print summary statistics."""
    if not results:
        return

    totals = [r["score"]["total"] for r in results]
    grades = [r["score"]["grade"] for r in results]

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"  {'='*60}")
    print(f"  Tests: {len(results)}")
    print(f"  Average: {sum(totals)/len(totals):.0f}/100")
    print(f"  Grades: {', '.join(grades)}")

    # By tier
    tiers = {}
    for r in results:
        tier = r["query"]["tier"]
        tiers.setdefault(tier, []).append(r["score"]["total"])

    print(f"\n  By Tier:")
    for tier, scores in sorted(tiers.items()):
        avg = sum(scores) / len(scores)
        threshold = SCORING.get(tier, {}).get("pass", 0.5) * 100
        status = "PASS" if avg >= threshold else "FAIL"
        print(f"    {tier}: {avg:.0f}/100 (threshold: {threshold:.0f}) [{status}]")


async def run_test(idx: int, query: dict) -> dict:
    """Run a single test query through Zenith."""
    from core.agent_loop import AgentLoop
    from core.codebook_compiler import CodebookCompiler
    from core.memory_compressor import MemoryCompressor
    from tools.builtin import BUILTIN_TOOLS
    from core.tools_manager import ToolsManager

    # Build minimal agent for testing
    tools_manager = ToolsManager()
    for name, fn in BUILTIN_TOOLS.items():
        tools_manager.register(name, fn)

    codebook = CodebookCompiler()

    # Simple LLM call function (uses the same config as main)
    from config.settings import Settings
    settings = Settings()
    settings.load_from_env()

    async def _llm_call(messages, compressed_context="", tools=None):
        """LLM call using httpx directly (same as main.py).

        The agent loop already injects system messages (physical constraints,
        skills, memory). We pass messages through as-is — no extra system prompt.
        """
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.reasoning.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.reasoning.model,
            "messages": messages,
            "max_tokens": 2000,
        }
        if tools:
            payload["tools"] = tools

        timeout = 15 if settings.reasoning.provider == "ollama" else 60

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.reasoning.base_url}/chat/completions",
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
            "model": data.get("model", settings.reasoning.model),
        }
        if "tool_calls" in message and message["tool_calls"]:
            result["tool_calls"] = message["tool_calls"]

        return result

    async def _compress_call(msgs):
        return {"content": ""}

    # Disable memory for tests to avoid contamination from previous runs
    class NoMemory:
        async def recall_with_trace(self, *args, **kwargs):
            return []
        async def compress_history(self, *args, **kwargs):
            return ""
        async def store_interaction(self, *args, **kwargs):
            pass

    memory_compressor = NoMemory()

    agent = AgentLoop(
        llm_call=_llm_call,
        tools_manager=tools_manager,
        memory_compressor=memory_compressor,
        codebook=codebook,
    )

    # Run in temporary directory to avoid corrupting project
    import tempfile
    import os
    from tools.builtin.file_ops import set_default_directory
    original_dir = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="zenith_test_") as tmpdir:
        os.chdir(tmpdir)
        set_default_directory(tmpdir)
        try:
            # Run with timeout
            start = time.time()
            try:
                result = await asyncio.wait_for(
                    agent.run(query["query"]),
                    timeout=query["max_time"] * 2,
                )
            except asyncio.TimeoutError:
                from core.types import ExecutionState
                result = ExecutionState(session_id="test", goal=query["query"], messages=[])
                result.final_response = "TIMEOUT"
            elapsed = time.time() - start
        finally:
            os.chdir(original_dir)
            set_default_directory(original_dir)

    return score_result(query, result, elapsed)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run SaaS coding tests")
    parser.add_argument("--tier", help="Run specific tier (T1, T2, T3, T4, T5)")
    parser.add_argument("--query", type=int, help="Run specific query by index")
    parser.add_argument("--dry-run", action="store_true", help="Print queries without running")
    args = parser.parse_args()

    queries = TEST_QUERIES
    if args.tier:
        tier_map = {"T1": "T1-Basic", "T2": "T2-Auth", "T3": "T3-FullStack", "T4": "T4-Complex", "T5": "T5-DevOps"}
        tier = tier_map.get(args.tier, args.tier)
        queries = [q for q in queries if q["tier"] == tier]
    if args.query is not None:
        queries = [queries[args.query]]

    if args.dry_run:
        for i, q in enumerate(queries):
            print(f"[{i}] {q['tier']}: {q['query']}")
        return

    print(f"Running {len(queries)} tests...")
    results = []

    for i, q in enumerate(queries):
        print(f"\n  Running [{i}] {q['tier']}...")
        try:
            score = await run_test(i, q)
            results.append({"query": q, "score": score})
            print_result(i, q, score)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"query": q, "score": {"total": 0, "grade": "F", "error": str(e)}})

    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
