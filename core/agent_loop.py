from __future__ import annotations
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.types import (
    AgentEvent, EventType, ExecutionState, CompiledAction,
    ToolResult, LocalLoopCircuitBreak, TokenBudgetExceeded
)
from core.flow_regulator import FlowRegulator
from core.safe_state import SafeState
from core.tools_manager import ToolsManager
from core.memory_compressor import MemoryCompressor
from core.codebook_compiler import CodebookCompiler
from core.failure_library import FailureLibrary
from core.emotional_engine import EmotionalEngine
from core.physical_intuition import PhysicalIntuition, ValidationLevel
from core.dual_channel import DualChannel
from core.state_steerer import StateSteerer
from core.intent_tracker import IntentTracker
from core.semantic_tool_router import SemanticToolRouter
from core.desire_engine import DesireEngine
from core.unrelated_association import UnrelatedAssociationEngine
from core.dream_controller import DreamController
from skills.loader import SkillLoader
from tts.zenith_tts import ZenithTTS
from filters.entropy_brake import EntropyBrake
from sandbox.permission_gate import PermissionGate, Decision
from sandbox.cow_projector import CowProjector
from sandbox.audit_log import AuditLog

log = logging.getLogger(__name__)


class AgentLoop:
    def __init__(
        self,
        llm_call: Callable,
        tools_manager: ToolsManager,
        memory_compressor: MemoryCompressor,
        codebook: Optional[CodebookCompiler] = None,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
        settings=None,
    ):
        self.llm_call = llm_call
        self.tools = tools_manager
        self.memory = memory_compressor
        self.codebook = codebook or CodebookCompiler()
        self.on_event = on_event or (lambda e: None)
        self.settings = settings
        self.regulator = FlowRegulator()
        self.safe_state = SafeState()
        self.entropy_brake = EntropyBrake()
        self.failure_lib = FailureLibrary()
        self.emotion = EmotionalEngine()
        self.physical = PhysicalIntuition()
        self.dual_channel = DualChannel(tts_engine=ZenithTTS())
        self.steerer = StateSteerer()
        self.intent_tracker = IntentTracker()
        self.skill_loader = SkillLoader()
        self.skill_loader.load_all()
        self.system_monitor = None  # Set externally if available

        # Desire + Association + Dream engines
        self.desire_engine = DesireEngine()
        self.association_engine = UnrelatedAssociationEngine()
        self.association_engine.seed_basic_concepts()
        self.dream_controller = DreamController(
            desire_engine=self.desire_engine,
            association_engine=self.association_engine,
            llm_call=llm_call,
            memory_compressor=memory_compressor,
        )
        self.permission_gate = PermissionGate(settings)
        self.cow_projector = CowProjector()
        self._proactive_context = []  # Recent memories for proactive injection
        self._proactive_suggestion = ""  # Brief suggestion when user returns
        self._recent_goals = []  # Track recent goals for repetition detection
        self._recent_tool_calls = []  # (func_name, args_hash) for dedup
        self._recently_written_files = set()  # Files written in this session — don't re-read

        # Tool schemas for native function calling
        self._tools_schema = self.codebook.get_tools_schema()
        self._risk_levels = self.codebook.get_risk_levels()

        # Semantic tool router — selects relevant tools per query (saves tokens)
        self.tool_router = SemanticToolRouter()
        self.tool_router.build_index(self._tools_schema)

        # Function name -> actual tool name mapping
        # Must match the names used in tools_manager.register() from BUILTIN_TOOLS
        self._func_to_tool = {
            "run_command": "run_command",
            "check_background": "check_background",
            "read_file": "read_file",
            "write_file": "write_file",
            "edit_file": "edit_file",
            "delete_file": "delete_file",
            "list_dir": "list_dir",
            "glob_search": "glob_search",
            "grep_search": "grep_search",
            "search": "search",
            "web_search": "search",
            "fetch": "fetch",
            "scrape": "scrape",
            "recall": "recall",
            "store_memory": "store_memory",
            "get_time": "get_time",
            "get_weather": "get_weather",
            "parse_document": "parse_document",
            "spreadsheet": "spreadsheet",
            "calendar": "calendar",
            "goals": "goals",
            "reminders": "reminders",
            "create_tool": "create_tool",
            "delete_dynamic_tool": "delete_dynamic_tool",
            "load_skill": "load_skill",
            # Browse.sh
            "browse_open": "browse_open",
            "browse_snapshot": "browse_snapshot",
            "browse_click": "browse_click",
            "browse_fill": "browse_fill",
            "browse_get": "browse_get",
            "browse_screenshot": "browse_screenshot",
            "browse_skills": "browse_skills",
            "browse_eval": "browse_eval",
            "browse_wait": "browse_wait",
            # PC Control
            "pc_get_windows": "pc_get_windows",
            "pc_get_ui_tree": "pc_get_ui_tree",
            "pc_click": "pc_click",
            "pc_fill": "pc_fill",
            "pc_press": "pc_press",
            "pc_screenshot": "pc_screenshot",
            "pc_launch": "pc_launch",
            "pc_focus": "pc_focus",
            # Subagent
            "dispatch_agent": "dispatch_agent",
            "dispatch_parallel": "dispatch_parallel",
            # Science Research Engine
            "science_research": "science_research",
            "analyze_molecule": "analyze_molecule",
            "check_battery_claim": "check_battery_claim",
            "check_fusion_lawson": "check_fusion_lawson",
            "compute_debye_length": "compute_debye_length",
        }

    async def run(self, goal: str, session_id: str = "",
                  autopilot: bool = False,
                  previous_messages: list = None) -> ExecutionState:
        """Main agent loop with native function calling.

        Keeps full message history. Model decides when to use tools.
        No regex parsing — model returns structured tool_calls.
        """
        import time as _time
        _start_time = _time.time()

        # Build messages list with conversation history
        messages = []
        if previous_messages:
            messages.extend(previous_messages)
        messages.append({"role": "user", "content": goal})

        state = ExecutionState(
            session_id=session_id,
            goal=goal,
            messages=messages,
            autopilot=autopilot,
            max_iterations=self.settings.max_iterations if self.settings else 30,
        )

        self._emit(EventType.THINKING, f"Thinking...", state)

        # Reset dedup tracker for new conversation
        self._recent_tool_calls = []

        # Track task in IntentTracker for cross-session continuity
        task_id = self.intent_tracker.create_task(goal, session_id)
        state.task_id = task_id

        # Signal user activity to SystemMonitor (if available)
        if self.system_monitor:
            self.system_monitor.signal_user_activity()
            # Start monitor on first run (if not already started)
            if not hasattr(self.system_monitor, '_started'):
                self.system_monitor._started = True
                import asyncio as _asyncio
                _asyncio.create_task(self.system_monitor.start())

        # Inject resume prompt from IntentTracker (unfinished task context)
        resume = self.intent_tracker.get_resume_prompt()
        if resume:
            # If user said yes/continue, mark task as resumed so it doesn't repeat
            continuation_words = {"yes", "y", "continue", "继续", "go", "do it", "sure", "ok"}
            if goal.strip().lower() in continuation_words:
                pending_id = self.intent_tracker.get_most_recent_pending_id()
                if pending_id:
                    self.intent_tracker.mark_resumed(pending_id)
            state.messages.append({
                "role": "system",
                "content": f"Unfinished task from last session: {resume}\nContinue directly — do NOT ask what to do."
            })

        # Recall memories — relevance-scored, empty result = no injection
        memories = await self.memory.recall_with_trace(goal, top_k=1)
        if memories:
            mem_context = memories[0]['content'][:300]
            state.messages.append({
                "role": "system",
                "content": f"Relevant context: {mem_context}"
            })

        # Inject zenith.md (agent instructions) into system prompt
        zenith_md = Path(__file__).resolve().parent.parent / "zenith.md"
        if zenith_md.exists():
            try:
                zenith_instructions = zenith_md.read_text(encoding="utf-8")[:2000]
                state.messages.insert(0, {
                    "role": "system",
                    "content": zenith_instructions
                })
            except Exception:
                pass

        # Inject user profile (language, preferences, communication style)
        user_profile_path = Path(__file__).resolve().parent.parent / "config" / "user_profile.yaml"
        if user_profile_path.exists():
            try:
                import yaml
                profile = yaml.safe_load(user_profile_path.read_text(encoding="utf-8"))
                profile_parts = []
                if profile.get("name"):
                    profile_parts.append(f"User: {profile['name']}")
                if profile.get("role"):
                    profile_parts.append(f"Role: {profile['role']}")
                if profile.get("communication_style"):
                    profile_parts.append(f"Style: {profile['communication_style']}")
                if profile.get("preferences"):
                    for pref in profile["preferences"]:
                        profile_parts.append(f"- {pref}")
                # Auto-detect language from user input
                has_cjk = any('一' <= c <= '鿿' for c in goal)
                if has_cjk:
                    profile_parts.append("User is writing in Chinese. Reply in Chinese.")
                if profile_parts:
                    state.messages.insert(0, {
                        "role": "system",
                        "content": "User profile:\n" + "\n".join(profile_parts)
                    })
            except Exception:
                pass

        # Inject all skills into system prompt — let the LLM decide which to follow
        all_skills = self.skill_loader.get_all_content()
        if all_skills:
            state.messages.insert(0, {
                "role": "system",
                "content": all_skills
            })

        # All tools available — LLM decides which to use
        _all_tools = self._tools_schema

        # Loop until LLM stops calling tools (like Claude Code — no hardcoded limit)
        # Safety limit only prevents infinite loops, not normal operation
        SAFETY_LIMIT = 100
        while state.iteration < SAFETY_LIMIT:
            state.iteration += 1

            # Capture safe state snapshot
            self.safe_state.capture(state)

            # Steering hints — warn model about resource limits
            if state.iteration > 2:
                steering = self.steerer.steer(state, [])
                if steering["hints"]:
                    state.messages.append({
                        "role": "system",
                        "content": " | ".join(steering["hints"]),
                    })

            # Compress context if approaching limits
            compressed = ""
            if state.tokens_used > state.token_budget * 0.6:
                compressed = await self.memory.compress_history(state.messages)
                state.compressed_context = compressed

            # Inject physical constraints + emotional state (returns empty if irrelevant)
            if state.iteration == 1:
                phys_constraints = self.physical.get_context_constraints(goal)
                emotion_hint = self.emotion.get_system_hint()
                context_parts = []
                if phys_constraints:
                    context_parts.append(phys_constraints)
                if emotion_hint:
                    context_parts.append(emotion_hint)
                if context_parts:
                    state.messages.insert(0, {
                        "role": "system",
                        "content": " ".join(context_parts),
                    })

                # Auto-inject research skill for research tasks
                research_keywords = ["research", "write about", "find information", "tell me about",
                                     "explain", "what is", "how does", "compare", "analyze",
                                     "study", "report", "paper", "article", "investigate"]
                goal_lower = goal.lower()
                if any(kw in goal_lower for kw in research_keywords):
                    research_skill = self.skill_loader.load_skill_content("research")
                    if "not found" not in research_skill.lower():
                        state.messages.insert(0, {
                            "role": "system",
                            "content": f"RESEARCH TASK DETECTED. You MUST follow this workflow:\n\n{research_skill}"
                        })

            # Call LLM with semantically selected tools (saves tokens)
            self._emit(EventType.THINKING, f"Thinking (step {state.iteration})...", state)
            # Include resume context in tool selection query
            selection_query = goal
            if resume:
                selection_query = f"{goal} {resume}"
            selected_tools = self.tool_router.select(selection_query, top_k=12)
            try:
                llm_response = await self.llm_call(
                    state.messages, compressed, tools=selected_tools
                )
            except Exception as e:
                self._emit(EventType.ERROR, f"LLM error: {e}", state)
                break

            content = llm_response.get("content", "")
            reasoning = llm_response.get("reasoning_content", "")
            tokens = llm_response.get("tokens_used", 0)
            state.tokens_used += tokens
            state.input_tokens += llm_response.get("prompt_tokens", 0)
            state.output_tokens += llm_response.get("completion_tokens", 0)

            # Handle Mimo's reasoning_content — if content is empty, use reasoning
            if not content.strip() and reasoning.strip():
                content = reasoning

            # Check for native tool_calls in response
            tool_calls = llm_response.get("tool_calls", [])

            # If model returned tool_calls, always execute them
            # (content may contain reasoning text, not the actual answer)

            # If empty response and no tools — retry WITHOUT tools
            # (some models return empty when given tools for simple queries)
            if not content.strip() and not tool_calls and state.iteration == 1:
                try:
                    llm_response = await self.llm_call(
                        state.messages, compressed, tools=None
                    )
                    content = llm_response.get("content", "")
                    reasoning = llm_response.get("reasoning_content", "")
                    tokens = llm_response.get("tokens_used", 0)
                    state.tokens_used += tokens
                    state.input_tokens += llm_response.get("prompt_tokens", 0)
                    state.output_tokens += llm_response.get("completion_tokens", 0)
                    if not content.strip() and reasoning.strip():
                        content = reasoning
                    tool_calls = llm_response.get("tool_calls", [])
                except Exception:
                    pass  # Keep original empty response

            if not tool_calls:
                # No tool calls — this is the final response
                state.final_response = content or ""
                state.goal_achieved = True
                self._emit(EventType.RESPONSE, state.final_response, state)
                break

            # Mid-task narration — emit content as progress if non-empty
            if content.strip():
                self._emit(EventType.RESPONSE, content.strip(), state)

            # Append assistant message with tool_calls to history
            assistant_msg = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = tool_calls
            state.messages.append(assistant_msg)

            # Execute each tool call
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                func_name = func.get("name", "")
                args_str = func.get("arguments", "{}")

                # Parse arguments
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}

                # Build CompiledAction for entropy brake / regulator
                action_token = f"ACT:{func_name.upper()}"
                call = CompiledAction(
                    token=action_token,
                    params=args,
                    execution_target=None,
                    confidence=1.0,
                    raw_input=content or "",
                )

                # Physical intuition: validate action BEFORE execution
                phys_verdict = self.physical.validate_action(func_name, args, goal)
                if phys_verdict.level == ValidationLevel.DENY:
                    AuditLog.record("blocked", func_name, args, "BLOCK",
                                    f"Physical: {phys_verdict.reason}", state.session_id)
                    self._emit(EventType.PERMISSION, phys_verdict.reason, state)
                    result = ToolResult(
                        success=False, tool_name=func_name,
                        error=f"Blocked: {phys_verdict.reason}"
                    )
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"Error: {phys_verdict.reason}",
                    })
                    state.tool_calls_made += 1
                    continue

                # Permission gate: three-tier decision (allow/confirm/block)
                gate_result = self.permission_gate.check(func_name, args)
                if gate_result.decision == Decision.BLOCK:
                    AuditLog.record("blocked", func_name, args, "BLOCK",
                                    gate_result.reason, state.session_id)
                    self._emit(EventType.PERMISSION,
                               f"[BLOCKED] {gate_result.reason}", state)
                    result = ToolResult(
                        success=False, tool_name=func_name,
                        error=f"Blocked: {gate_result.reason}"
                    )
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"Error: {gate_result.reason}",
                    })
                    state.tool_calls_made += 1
                    continue

                # Entropy brake: check for irreversible actions
                brake = self.entropy_brake.check(action_token, args)
                if brake.requires_confirmation:
                    AuditLog.record("entropy_brake", func_name, args, "CONFIRM",
                                    brake.reason, state.session_id)
                    if not state.autopilot:
                        self._emit(EventType.PERMISSION, brake.reason, state)
                        result = ToolResult(
                            success=False, tool_name=func_name,
                            error=f"Denied: {brake.reason}"
                        )
                    else:
                        # Autopilot: allow but log the warning
                        AuditLog.record("autopilot_override", func_name, args,
                                        "ALLOWED", f"Autopilot override: {brake.reason}", state.session_id)
                else:
                    # Regulator check — catch budget exceeded gracefully
                    try:
                        self.regulator.check_action(state, action_token, args)
                    except TokenBudgetExceeded:
                        self._emit(EventType.ERROR, "Token budget reached. Stopping.", state)
                        if not state.final_response:
                            state.final_response = "I've used too many tokens on this task. Try breaking it into smaller steps."
                        state.goal_achieved = False
                        break

                    # Dedup: block repeated identical tool calls
                    import hashlib
                    call_key = f"{func_name}:{json.dumps(args, sort_keys=True)}"
                    call_hash = hashlib.md5(call_key.encode()).hexdigest()[:12]
                    call_count = sum(1 for h in self._recent_tool_calls if h == call_hash)

                    # Special: block read_file after 1 call (save tokens)
                    if func_name == "read_file" and call_count >= 1:
                        result = ToolResult(
                            success=False, tool_name=func_name,
                            error=f"Blocked: you already read this file. Use the content you already have. Do NOT re-read files."
                        )
                        state.messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": f"Error: You already read this file. Use the content you already have. If you need to modify it, use edit_file directly.",
                        })
                        state.tool_calls_made += 1
                        self._emit(EventType.OBSERVATION, f"Blocked re-read: {func_name}", state)
                        continue

                    # Block reading files that were just written (you already know the content)
                    if func_name == "read_file" and "path" in args:
                        if args["path"] in self._recently_written_files:
                            result = ToolResult(
                                success=False, tool_name=func_name,
                                error=f"Blocked: you just wrote this file. You already know its content. Do NOT read it."
                            )
                            state.messages.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "content": f"Error: You just wrote {args['path']}. You already know its content. Use edit_file to modify it or move on.",
                            })
                            state.tool_calls_made += 1
                            self._emit(EventType.OBSERVATION, f"Blocked read-after-write: {func_name}", state)
                            continue

                    if call_count >= 2:
                        result = ToolResult(
                            success=False, tool_name=func_name,
                            error=f"Blocked: you already called {func_name} with these args {call_count} times. Try something different."
                        )
                        state.messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": f"Error: You already called {func_name} with these exact args {call_count} times. The result hasn't changed. Try a different approach.",
                        })
                        state.tool_calls_made += 1
                        self._emit(EventType.OBSERVATION, f"Blocked duplicate: {func_name}", state)
                        continue
                    self._recent_tool_calls.append(call_hash)
                    # Keep only last 30 calls
                    if len(self._recent_tool_calls) > 30:
                        self._recent_tool_calls = self._recent_tool_calls[-30:]

                    # Map function name to actual tool
                    tool_name = self._func_to_tool.get(func_name, func_name)

                    # Emit ACTION event with parameters visible
                    # Use intent field if provided, otherwise infer from params
                    intent = args.pop("intent", "")
                    action_display = func_name
                    if intent:
                        action_display = f"{func_name}: {intent[:80]}"
                    elif func_name == "run_command" and "command" in args:
                        action_display = f"run_command: {args['command'][:80]}"
                    elif func_name in ("write_file", "read_file", "edit_file", "delete_file") and "path" in args:
                        action_display = f"{func_name}: {args['path'][:60]}"
                    elif "query" in args:
                        action_display = f"{func_name}: {args['query'][:60]}"
                    elif "url" in args:
                        action_display = f"{func_name}: {args['url'][:60]}"
                    elif "content" in args and func_name == "store_memory":
                        action_display = f"store_memory: {args['content'][:60]}"
                    self._emit(EventType.ACTION, f"Executing: {action_display}", state)

                    # Dual channel: speak while executing (if enabled)
                    if (self.settings and self.settings.dual_channel_enabled and
                        self.dual_channel._tts):
                        speak_text = f"Using {func_name}"
                        result = await self.dual_channel.speak_while_executing(
                            speak_text, self.tools.execute(tool_name, args)
                        )
                    else:
                        # Execute tool normally
                        result = await self.tools.execute(tool_name, args)

                    # Record tool usage for semantic router recency scoring
                    self.tool_router.record_usage(tool_name)

                    # Audit log for executed action
                    AuditLog.record("executed", func_name, args,
                                    "ALLOW" if result.success else "FAILED",
                                    f"success={result.success}", state.session_id)

                    # Track written files to prevent re-reading
                    if func_name == "write_file" and result.success and "path" in args:
                        self._recently_written_files.add(args["path"])

                state.tool_calls_made += 1

                # Reflection checkpoint: every 5 tool calls, force agent to assess progress
                if state.tool_calls_made % 5 == 0:
                    state.messages.append({
                        "role": "system",
                        "content": (
                            f"REFLECTION: {state.tool_calls_made} tool calls made. "
                            f"Stop reading files you already have. Give the user an answer NOW based on what you've seen."
                        ),
                    })

                # Research task check: ensure search tools are used
                research_keywords = ["research", "write about", "find information", "tell me about",
                                     "explain", "what is", "how does", "compare", "analyze",
                                     "study", "report", "paper", "article", "investigate"]
                is_research_task = any(kw in goal.lower() for kw in research_keywords)
                if is_research_task and state.tool_calls_made == 3:
                    # Check if search tools were used
                    search_used = False
                    for msg in state.messages:
                        if msg.get("role") == "assistant" and "tool_calls" in msg:
                            for tc in msg["tool_calls"]:
                                if tc.get("function", {}).get("name", "") in ("search", "scrape", "fetch"):
                                    search_used = True
                                    break
                    if not search_used:
                        state.messages.append({
                            "role": "system",
                            "content": "RESEARCH TASK: You haven't used search tools yet. You MUST call 'search' to find information before writing. Do NOT write from memory alone."
                        })

                # Hard stop: too many tool calls — force a response
                if state.tool_calls_made >= 12:
                    state.messages.append({
                        "role": "system",
                        "content": "STOP. You've made too many tool calls. Give a final answer based on what you know right now.",
                    })

                # Update emotional state
                self.emotion.update("success" if result.success else "error")

                # Format observation — full content for LLM, summary for user display
                if result.success:
                    obs = str(result.data)[:1000] if result.data else "OK"
                else:
                    obs = f"Error: {result.error or 'Command failed'}"

                # Append full tool result to messages (LLM needs the details)
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": obs,
                })

                # Emit summary to user — NOT the full content
                if func_name == "read_file" and result.success:
                    data = result.data or {}
                    total = data.get("total_lines", "?")
                    path_display = data.get("path", args.get("path", ""))
                    display = f"Read {path_display} ({total} lines)"
                elif func_name == "run_command" and result.success:
                    data = result.data or {}
                    rc = data.get("returncode", 0)
                    stdout = data.get("stdout", "")
                    # Show first 2 lines of output, not everything
                    preview = "\n".join(stdout.split("\n")[:2])
                    if len(stdout.split("\n")) > 2:
                        preview += "..."
                    display = f"Command done (exit {rc}): {preview[:120]}"
                elif func_name == "edit_file" and result.success:
                    data = result.data or {}
                    display = f"Edited {data.get('path', '')} ({data.get('lines_changed', 0)} lines changed)"
                elif func_name == "write_file" and result.success:
                    data = result.data or {}
                    display = f"Wrote {data.get('path', '')} ({data.get('bytes_written', 0)} bytes)"
                elif func_name == "list_dir" and result.success:
                    data = result.data or {}
                    display = f"Listed {data.get('path', '')} ({data.get('count', 0)} entries)"
                elif func_name == "browse_snapshot" and result.success:
                    display = f"Page snapshot captured"
                elif func_name == "browse_screenshot" and result.success:
                    # Save screenshot and auto-open for user
                    import base64, os, time, subprocess, sys
                    data = result.data or {}
                    # browse CLI may nest the base64 in different places
                    b64 = data.get("base64", "")
                    if not b64 and isinstance(data, dict):
                        # Try nested: data.data.base64
                        inner = data.get("data", {})
                        if isinstance(inner, dict):
                            b64 = inner.get("base64", "")
                    if b64:
                        try:
                            img_bytes = base64.b64decode(b64)
                            ss_dir = str(Path.home() / ".zenith")
                            os.makedirs(ss_dir, exist_ok=True)
                            ss_path = os.path.join(ss_dir, f"screenshot_{int(time.time())}.png")
                            with open(ss_path, "wb") as f:
                                f.write(img_bytes)
                            display = f"Screenshot saved: {ss_path}"
                            # Auto-open on Windows
                            if sys.platform == "win32":
                                os.startfile(ss_path)
                        except Exception as e:
                            display = f"Screenshot captured (save failed: {e})"
                    else:
                        display = "Screenshot captured (no image data in response)"
                elif func_name in ("browse_click", "browse_fill") and result.success:
                    display = f"{func_name} succeeded"
                else:
                    display = obs[:200]
                self._emit(EventType.OBSERVATION, display, state)

                # Check for failure and inject recovery hint
                if not result.success:
                    # Desire engine: observe failures as knowledge gaps
                    self.desire_engine.observe(
                        "error",
                        f"{func_name} failed: {result.error or 'unknown error'}",
                        source=f"tool_call_{state.tool_calls_made}",
                    )
                    hint = self.failure_lib.get_recovery_hint(result.error or "")
                    if hint:
                        state.messages.append({
                            "role": "system",
                            "content": hint,
                        })

                    # Safe state rollback: if we have a previous snapshot, restore message count
                    snapshot = self.safe_state.latest()
                    if snapshot and len(state.messages) > snapshot.message_history_length + 5:
                        # Trim messages back to snapshot point + recent context
                        state.messages = state.messages[:snapshot.message_history_length] + state.messages[-3:]
                        self._emit(EventType.COMPRESSED,
                                   f"Rolled back to snapshot {snapshot.id[:8]}", state)
                else:
                    # After successful tool use, only intervene for specific cases
                    if func_name == "web_search" and state.tool_calls_made >= 5:
                        state.messages.append({
                            "role": "system",
                            "content": "You have enough search results. Give a clear answer now.",
                        })

        # Research verification: check if research tasks actually used search tools
        research_keywords = ["research", "write about", "find information", "tell me about",
                             "explain", "what is", "how does", "compare", "analyze",
                             "study", "report", "paper", "article", "investigate"]
        is_research_task = any(kw in goal.lower() for kw in research_keywords)
        if is_research_task and state.goal_achieved:
            # Check if search/scrape tools were actually used
            search_tools_used = set()
            for msg in state.messages:
                if msg.get("role") == "assistant" and "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        func_name = tc.get("function", {}).get("name", "")
                        if func_name in ("search", "scrape", "fetch"):
                            search_tools_used.add(func_name)
            if not search_tools_used:
                # Agent didn't use search tools for research task — warn
                state.final_response = (
                    "WARNING: This was a research task but no web search tools were used. "
                    "The following response may contain unverified information.\n\n"
                    + state.final_response
                )
                self._emit(EventType.ERROR,
                           "Research task completed without using search tools", state)
                # Desire engine: knowledge gap — agent relied on memory for research
                self.desire_engine.observe(
                    "knowledge_gap",
                    f"Research task '{goal[:100]}' completed without web search — may contain hallucinated facts",
                    source="research_verification",
                )

        # Desire engine: observe incomplete tasks
        if not state.goal_achieved:
            self.desire_engine.observe(
                "incomplete",
                f"Task not fully achieved: {goal[:150]}",
                source=f"session_{session_id}",
            )

        # Store interaction in memory
        if state.goal_achieved:
            await self.memory.store_interaction(
                goal, state.final_response, session_id,
                tool_calls_made=state.tool_calls_made,
                last_tool_token="",
            )

        # Complete task in IntentTracker
        summary = (state.final_response[:200] if state.final_response
                   else f"Completed after {state.tool_calls_made} tool calls")
        self.intent_tracker.complete_task(task_id, summary)

        self._emit(EventType.DONE, "Complete", state)

        # Self-evaluation - score this interaction
        from core.self_evaluation import evaluate
        duration = _time.time() - _start_time
        error_count = sum(
            1 for m in state.messages
            if m.get("role") == "tool" and "Error" in m.get("content", "")
        )

        # Repetition detection — how many times user asked similar thing
        goal_words = set(goal.lower().split())
        repeat_count = 0
        for prev_goal in self._recent_goals:
            prev_words = set(prev_goal.lower().split())
            overlap = len(goal_words & prev_words) / max(len(goal_words | prev_words), 1)
            if overlap > 0.6:
                repeat_count += 1
        self._recent_goals.append(goal)
        if len(self._recent_goals) > 20:
            self._recent_goals = self._recent_goals[-20:]

        state._eval = evaluate(
            goal=goal,
            tool_calls=state.tool_calls_made,
            tokens_used=state.tokens_used,
            response_len=len(state.final_response),
            goal_achieved=state.goal_achieved,
            had_error=error_count > 0,
            duration=duration,
            input_tokens=state.input_tokens,
            output_tokens=state.output_tokens,
            error_count=error_count,
            repeat_count=repeat_count,
        )

        return state

    def _emit(self, event_type: EventType, content: str, state: ExecutionState):
        event = AgentEvent(
            type=event_type,
            content=content,
            session_id=state.session_id,
            metadata={"iteration": state.iteration, "tokens": state.tokens_used}
        )
        self.on_event(event)
