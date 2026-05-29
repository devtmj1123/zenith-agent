"""Subagent — dispatch sub-tasks to parallel agent instances.

Provides: dispatch_agent — runs a sub-task in a fresh agent loop with its own context.
"""
from __future__ import annotations
import asyncio
import json
import uuid
from typing import Optional


async def dispatch_agent(params: dict) -> dict:
    """Dispatch a sub-task to a fresh agent instance.

    params: {task: str, context?: str, tools?: list[str], max_iterations?: int}
    Returns the sub-agent's final response.
    """
    task = params.get("task")
    if not task:
        return {"success": False, "error": "Missing 'task' parameter"}

    context = params.get("context", "")
    allowed_tools = params.get("tools")
    max_iterations = params.get("max_iterations", 15)

    try:
        # Import here to avoid circular imports
        from main import build_agent, Settings

        settings = Settings()
        settings.load_from_env()

        # Build a fresh agent for the sub-task
        agent = build_agent(settings)

        # If specific tools are requested, filter the tool schema
        if allowed_tools:
            filtered_schema = [
                t for t in agent._tools_schema
                if t.get("function", {}).get("name", "") in allowed_tools
            ]
            agent._tools_schema = filtered_schema

        # Build the sub-task prompt
        sub_task = task
        if context:
            sub_task = f"Context:\n{context}\n\nTask:\n{task}"

        # Run the sub-agent
        result = await agent.run(sub_task, session_id=f"sub-{uuid.uuid4().hex[:8]}")

        return {
            "success": True,
            "data": {
                "response": result.final_response,
                "iterations": result.iteration,
                "tool_calls": result.tool_calls_made,
                "tokens_used": result.tokens_used,
                "goal_achieved": result.goal_achieved,
            }
        }

    except Exception as e:
        return {"success": False, "error": f"Sub-agent error: {str(e)}"}


async def dispatch_parallel(params: dict) -> dict:
    """Dispatch multiple sub-tasks in parallel.

    params: {tasks: list[{task: str, context?: str}], max_iterations?: int}
    Returns results from all sub-agents.
    """
    tasks = params.get("tasks")
    if not tasks or not isinstance(tasks, list):
        return {"success": False, "error": "Missing 'tasks' parameter (list)"}

    max_iterations = params.get("max_iterations", 15)

    async def _run_one(task_spec: dict) -> dict:
        return await dispatch_agent({
            "task": task_spec.get("task", ""),
            "context": task_spec.get("context", ""),
            "max_iterations": max_iterations,
        })

    try:
        results = await asyncio.gather(*[_run_one(t) for t in tasks])
        return {
            "success": True,
            "data": {
                "results": results,
                "total": len(results),
                "succeeded": sum(1 for r in results if r.get("success")),
            }
        }
    except Exception as e:
        return {"success": False, "error": f"Parallel dispatch error: {str(e)}"}
