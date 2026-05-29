from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
import time


class EventType(str, Enum):
    THINKING    = "thinking"
    ACTION      = "action"
    OBSERVATION = "observation"
    RESPONSE    = "response"
    ERROR       = "error"
    DONE        = "done"
    PERMISSION  = "permission"
    COMPRESSED  = "compressed"
    HEARTBEAT   = "heartbeat"
    DREAM       = "dream"
    PROACTIVE   = "proactive"


@dataclass
class AgentEvent:
    type: EventType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""


@dataclass
class CompiledAction:
    token: str
    params: dict
    execution_target: Optional[str]
    confidence: float
    raw_input: str = ""


@dataclass
class ExecutionState:
    session_id: str
    goal: str
    messages: List[Dict[str, Any]]
    iteration: int = 0
    max_iterations: int = 30  # Overridden by settings.max_iterations in agent_loop
    tool_calls_made: int = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_budget: int = 200_000
    compressed_context: str = ""
    final_response: str = ""
    goal_achieved: bool = False
    debug: bool = False
    autopilot: bool = False
    intent_type: str = "unknown"
    task_id: Optional[str] = None


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    data: Any = None
    error: Optional[str] = None
    tokens_consumed: int = 0


class RegulatorDecision(str, Enum):
    ALLOW   = "allow"
    DENY    = "deny"
    CONFIRM = "confirm"


@dataclass
class RegulatorVerdict:
    decision: RegulatorDecision
    reason: str


PluginFn = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class SafeStateSnapshot:
    id: str
    timestamp: float = field(default_factory=time.time)
    completed_summary: str = ""
    pending_action: str = ""
    message_history_length: int = 0
    tool_calls_made: int = 0
    tokens_used: int = 0


@dataclass
class TaskNode:
    task_id: str
    goal: str
    status: str = "pending"
    progress_summary: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    session_ids: List[str] = field(default_factory=list)


class LocalLoopCircuitBreak(Exception):
    def __init__(self, action_hash: str, count: int):
        self.action_hash = action_hash
        self.count = count
        super().__init__(f"Circuit break: {action_hash[:8]} repeated {count}x")


class TokenBudgetExceeded(Exception):
    pass


class DimensionMissingError(Exception):
    pass
