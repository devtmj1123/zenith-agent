"""Self-evaluation — per-message scoring for Zenith self-improvement.

Formula: Score = (Intent x 0.35) + (Efficiency x 0.35) + (Quality x 0.30) - Penalties

Where:
  Intent     = did the agent understand what the user wanted?
  Efficiency = tokens used relative to task complexity (denominator-based)
  Quality    = was the result good? (LLM-judged if enabled, heuristic fallback)
  Penalties  = errors, repetition, overkill

No speed/time — that's infrastructure, not intelligence.

Per-session logs saved to .zenith/eval_logs/YYYY-MM-DD.jsonl
Nightly analysis aggregates by category for self-improvement.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class EvalResult:
    intent_score: float
    efficiency_score: float
    quality_score: float
    penalties: float
    penalty_details: str
    input_tokens: int
    output_tokens: int
    total: float
    grade: str
    feedback: str

    def display(self) -> str:
        bar = _bar(self.total)
        lines = [
            f"  \033[90m+-- Score: {self.total:.0f}/100 {self.grade} {bar}",
            f"  |  Intent: {self.intent_score:.0f}  Eff: {self.efficiency_score:.0f}  "
            f"Quality: {self.quality_score:.0f}",
            f"  |  Tokens: {self.input_tokens} in / {self.output_tokens} out",
        ]
        if self.penalties > 0:
            lines.append(f"  |  Penalties: -{self.penalties:.0f} ({self.penalty_details})")
        lines.append(f"  +-- {self.feedback}")
        return "\n".join(lines)


def _bar(score: float, width: int = 10) -> str:
    filled = int(score / 100 * width)
    return f"[{'#' * filled}{'.' * (width - filled)}]"


def _grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 40: return "D"
    return "F"


def _intent_score(goal: str, tool_calls: int, goal_achieved: bool) -> float:
    """Did the agent understand what was wanted?

    - Simple goal + no tools = good (direct answer)
    - Complex goal + tools = good (using resources)
    - Simple goal + many tools = overkill
    - Complex goal + no tools = probably missed something
    """
    goal_len = len(goal.strip())
    is_simple = goal_len < 30

    if goal_achieved:
        base = 85.0
    else:
        base = 40.0

    # Simple goal: penalize excessive tool use
    if is_simple and tool_calls > 3:
        base -= 20
    # Complex goal: penalize no tool use (likely didn't do the work)
    elif not is_simple and tool_calls == 0 and goal_achieved:
        base -= 10  # Might be a knowledge question, light penalty

    return max(0, min(100, base))


def _efficiency_score(tokens_used: int, tool_calls: int, response_len: int,
                      goal_complexity: int) -> float:
    """Token efficiency — tokens relative to task complexity.

    Not just "fewer = better" — a complex task SHOULD use more tokens.
    The question is: were the tokens proportional to the task?

    efficiency = expected_tokens / actual_tokens (capped at 1.0)
    """
    # Base overhead: system prompt + history + tools + API overhead
    base_overhead = 1500

    # Variable tokens based on goal complexity
    if goal_complexity < 30:
        variable = 300    # Simple: direct answer, maybe 1 tool
    elif goal_complexity < 100:
        variable = 2000   # Medium: multiple tool calls, code generation
    else:
        variable = 5000   # Complex: many tool calls, full project builds

    # Multiplier for tool calls — each tool call uses ~500-1000 tokens for context
    tool_overhead = tool_calls * 400

    expected = base_overhead + variable + tool_overhead

    if tokens_used <= 0:
        return 80.0  # No data, assume OK

    ratio = expected / tokens_used
    # ratio > 1 = more efficient than expected (good)
    # ratio < 1 = less efficient than expected (bad)
    score = min(100, ratio * 80)

    return max(0, min(100, score))


def _quality_score(goal_achieved: bool, had_error: bool, tool_calls: int,
                   response_len: int) -> float:
    """Quality heuristic — used when LLM scoring is disabled.

    This is the fallback. With LLM scoring, the LLM judges quality directly.
    """
    if not goal_achieved:
        return 30.0

    score = 75.0
    if not had_error:
        score += 15
    if response_len > 50:
        score += 5
    if tool_calls > 6:
        score -= 10

    return max(0, min(100, score))


def _calc_penalties(goal: str, tool_calls: int, tokens_used: int,
                    goal_achieved: bool, error_count: int,
                    repeat_count: int = 0) -> tuple[float, str]:
    """Calculate penalties for bad behavior.

    Repeat count: how many times the user asked the same/similar thing.
    High repetition = agent is failing to learn or adapt.
    """
    penalties = 0.0
    details = []

    if error_count > 0:
        p = error_count * 10
        penalties += p
        details.append(f"{error_count} errors (-{p})")

    # Overkill: short question with no tools that used lots of tokens
    # Don't penalize if tools were used — that's real work
    if len(goal.strip()) < 20 and tokens_used > 2000 and tool_calls == 0:
        penalties += 15
        details.append("overkill (-15)")

    if not goal_achieved:
        penalties += 20
        details.append("not achieved (-20)")

    if tool_calls > 15:
        penalties += 10
        details.append("too many tools (-10)")

    # Repetition penalty — user asked same thing before
    if repeat_count > 0:
        p = min(repeat_count * 15, 45)  # Cap at -45
        penalties += p
        details.append(f"repeat x{repeat_count} (-{p})")

    return penalties, ", ".join(details) if details else "none"


def _feedback(total: float, intent: float, efficiency: float,
              quality: float, penalties: float) -> str:
    if total >= 90:
        return "Excellent - efficient and effective"
    if total >= 75:
        if efficiency < 60:
            return "Good result, but used more tokens than needed"
        return "Good - task completed well"
    if total >= 60:
        if intent < 60:
            return "OK - might have misunderstood the request"
        return "OK - acceptable but room to improve"
    if total >= 40:
        if penalties > 20:
            return "Below average - errors and penalties hurt score"
        return "Below average - too many resources used"
    return "Poor - need to rethink approach"


def evaluate(goal: str, tool_calls: int, tokens_used: int,
             response_len: int, goal_achieved: bool,
             had_error: bool, duration: float = 0,
             input_tokens: int = 0, output_tokens: int = 0,
             error_count: int = 0, repeat_count: int = 0,
             llm_quality_score: float = 0) -> EvalResult:
    """Evaluate agent performance on a single message.

    Args:
        repeat_count: how many times user asked similar thing this session
        llm_quality_score: if LLM quality scoring enabled, the score (0-100)
    """
    goal_len = len(goal.strip())

    i = _intent_score(goal, tool_calls, goal_achieved)
    e = _efficiency_score(tokens_used, tool_calls, response_len, goal_len)

    # Use LLM quality score if available, otherwise heuristic
    if llm_quality_score > 0:
        q = llm_quality_score
    else:
        q = _quality_score(goal_achieved, had_error, tool_calls, response_len)

    base = i * 0.35 + e * 0.35 + q * 0.30

    penalties, penalty_details = _calc_penalties(
        goal, tool_calls, tokens_used, goal_achieved, error_count, repeat_count
    )

    total = max(0, min(100, base - penalties))

    return EvalResult(
        intent_score=i,
        efficiency_score=e,
        quality_score=q,
        penalties=penalties,
        penalty_details=penalty_details,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total=total,
        grade=_grade(total),
        feedback=_feedback(total, i, e, q, penalties),
    )


# --- Nightly Analysis ---

def analyze_daily_log(date_str: str = None) -> dict:
    """Analyze a day's evaluation log for self-improvement.

    Returns aggregated scores by category:
    - avg_intent, avg_efficiency, avg_quality, avg_total
    - total_tokens, total_tool_calls
    - repeat_patterns (goals asked multiple times)
    - worst_messages (lowest scores)
    """
    if date_str is None:
        date_str = time.strftime("%Y-%m-%d")

    log_file = Path.home() / ".zenith" / "eval_logs" / f"{date_str}.jsonl"
    if not log_file.exists():
        return {"error": f"No log file for {date_str}"}

    entries = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if not entries:
        return {"error": "Empty log"}

    # Aggregates
    n = len(entries)
    avg_intent = sum(e["intent"] for e in entries) / n
    avg_efficiency = sum(e["efficiency"] for e in entries) / n
    avg_quality = sum(e["quality"] for e in entries) / n
    avg_total = sum(e["total"] for e in entries) / n
    total_input = sum(e["input_tokens"] for e in entries)
    total_output = sum(e["output_tokens"] for e in entries)
    total_tools = sum(e["tool_calls"] for e in entries)

    # Repeat patterns — similar goals
    from collections import Counter
    goal_words = Counter()
    for e in entries:
        words = set(e["goal"].lower().split()[:5])  # First 5 words
        for w in words:
            if len(w) > 3:
                goal_words[w] += 1
    repeats = {w: c for w, c in goal_words.most_common(10) if c > 1}

    # Worst messages
    sorted_entries = sorted(entries, key=lambda x: x["total"])
    worst = sorted_entries[:3]

    return {
        "date": date_str,
        "messages": n,
        "avg_intent": round(avg_intent, 1),
        "avg_efficiency": round(avg_efficiency, 1),
        "avg_quality": round(avg_quality, 1),
        "avg_total": round(avg_total, 1),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tool_calls": total_tools,
        "repeat_patterns": repeats,
        "worst_messages": [
            {"goal": w["goal"][:60], "score": w["total"], "grade": w["grade"]}
            for w in worst
        ],
    }
