from __future__ import annotations
import asyncio
import logging
import time
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
from filters.entropy_brake import EntropyBrake

log = logging.getLogger(__name__)


class AgentLoop:
    def __init__(
        self,
        llm_call: Callable,
        tools_manager: ToolsManager,
        memory_compressor: MemoryCompressor,
        codebook: Optional[CodebookCompiler] = None,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
    ):
        self.llm_call = llm_call
        self.tools = tools_manager
        self.memory = memory_compressor
        self.codebook = codebook or CodebookCompiler()
        self.on_event = on_event or (lambda e: None)
        self.regulator = FlowRegulator()
        self.safe_state = SafeState()
        self.entropy_brake = EntropyBrake()
        self.failure_lib = FailureLibrary()

    async def run(self, goal: str, session_id: str = "",
                  autopilot: bool = False) -> ExecutionState:
        """Main ReAct loop."""
        state = ExecutionState(
            session_id=session_id,
            goal=goal,
            messages=[{"role": "user", "content": goal}],
            autopilot=autopilot,
        )

        self._emit(EventType.THINKING, f"Processing: {goal[:100]}", state)

        # Recall relevant memories before first LLM call
        memories = await self.memory.recall_with_trace(goal, top_k=3)
        if memories:
            mem_context = "\n".join(f"- {m['content'][:200]}" for m in memories)
            state.messages.insert(1, {
                "role": "system",
                "content": f"Relevant memories:\n{mem_context}"
            })

        while state.iteration < state.max_iterations:
            state.iteration += 1

            # Capture safe state snapshot
            self.safe_state.capture(state)

            # Compress context if approaching limits
            compressed = ""
            if state.tokens_used > state.token_budget * 0.6:
                compressed = await self.memory.compress_history(state.messages)
                state.compressed_context = compressed

            # Call LLM
            try:
                llm_response = await self.llm_call(state.messages, compressed)
            except Exception as e:
                self._emit(EventType.ERROR, f"LLM error: {e}", state)
                break

            content = llm_response.get("content", "")
            tokens = llm_response.get("tokens_used", 0)
            state.tokens_used += tokens

            # Parse tool calls from response
            tool_calls = self._extract_tool_calls(content)

            if not tool_calls:
                # No tool calls — this is the final response
                state.final_response = content
                state.goal_achieved = True
                self._emit(EventType.RESPONSE, content, state)
                break

            # Execute tool calls
            for call in tool_calls:
                try:
                    result = await self._execute_tool(state, call)
                    state.tool_calls_made += 1

                    # Add observation to messages
                    observation = self._format_observation(call, result)
                    state.messages.append({"role": "assistant", "content": f"I'll {call.token}"})
                    state.messages.append({"role": "user", "content": observation})

                    self._emit(EventType.OBSERVATION, observation, state)

                    # Check for failure and apply recovery
                    if not result.success:
                        hint = self.failure_lib.get_recovery_hint(result.error or "")
                        if hint:
                            state.messages.append({"role": "system", "content": hint})

                except LocalLoopCircuitBreak as e:
                    self._emit(EventType.ERROR, str(e), state)
                    state.final_response = f"Stopped: {e}"
                    return state
                except TokenBudgetExceeded as e:
                    self._emit(EventType.ERROR, str(e), state)
                    state.final_response = f"Token budget exceeded: {e}"
                    return state

        # Store interaction in memory
        if state.goal_achieved:
            await self.memory.store_interaction(goal, state.final_response, session_id)

        self._emit(EventType.DONE, "Complete", state)
        return state

    async def _execute_tool(self, state: ExecutionState,
                            call: CompiledAction) -> ToolResult:
        """Execute a single tool call with entropy brake check."""
        # Entropy brake: check for irreversible actions
        brake = self.entropy_brake.check(call.token, call.params)
        if brake.requires_confirmation:
            if not state.autopilot:
                self._emit(EventType.PERMISSION, brake.reason, state)
                # In non-autopilot, would wait for user confirmation
                # For now, deny irreversible actions in autonomous mode
                return ToolResult(
                    success=False, tool_name=call.token,
                    error=f"Denied: {brake.reason}"
                )

        # Regulator check
        self.regulator.check_action(state, call.token, call.params)

        # Execute — strip ACT: prefix for tool lookup
        tool_name = call.token.replace("ACT:", "").lower() if call.token.startswith("ACT:") else call.token
        result = await self.tools.execute(tool_name, call.params)
        return result

    def _extract_tool_calls(self, content: str) -> List[CompiledAction]:
        """Extract tool calls from LLM response."""
        import re
        calls = []

        # Pattern: ACT:TOKEN or tool_name(params)
        patterns = [
            (r'ACT:(\w+)', lambda m: CompiledAction(
                token=f"ACT:{m.group(1)}", params={"_context": content},
                execution_target=None, confidence=0.8
            )),
            (r'(\w+)\(([^)]*)\)', lambda m: CompiledAction(
                token=m.group(1), params={"raw": m.group(2)},
                execution_target=None, confidence=0.7
            )),
        ]

        for pattern, builder in patterns:
            for match in re.finditer(pattern, content):
                compiled = self.codebook.compile(match.group(0))
                if compiled:
                    compiled.params.setdefault("_context", content)
                    calls.append(compiled)
                else:
                    calls.append(builder(match))

        return calls

    def _format_observation(self, call: CompiledAction, result: ToolResult) -> str:
        """Format tool result as observation message."""
        if result.success:
            data_str = str(result.data)[:500] if result.data else "OK"
            return f"[{call.token}] Success: {data_str}"
        else:
            return f"[{call.token}] Failed: {result.error}"

    def _emit(self, event_type: EventType, content: str, state: ExecutionState):
        event = AgentEvent(
            type=event_type,
            content=content,
            session_id=state.session_id,
            metadata={"iteration": state.iteration, "tokens": state.tokens_used}
        )
        self.on_event(event)
