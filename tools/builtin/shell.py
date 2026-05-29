import asyncio
import os
import re
import sys
import uuid
from pathlib import Path


# Default working directory — set to current working directory
_DEFAULT_DIR = os.getcwd()

# Background task storage
_background_tasks: dict = {}


def set_default_directory(path: str):
    """Set the default working directory for shell commands."""
    global _DEFAULT_DIR
    _DEFAULT_DIR = str(Path(path).resolve())


async def run_command(params: dict) -> dict:
    """Execute shell command.

    params: {command: str, timeout: int=120, stdin: str, run_in_background: bool}
    """
    command = params.get("command")
    stdin_data = params.get("stdin")
    run_in_background = params.get("run_in_background", False)

    # If no explicit command, try to extract from LLM context
    if not command:
        context = params.get("_context", "")
        for pattern in [
            r'(?:run|execute|command)[:\s]+`?([^`\n]+)`?',
            r'```\w*\n?(.+?)```',
            r'(?:ls|dir|cat|echo|pip|python|git|mkdir|rm|cp|mv|curl|ping)\s+[^\n]+',
        ]:
            m = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
            if m:
                command = m.group(1).strip()
                break

    if not command:
        return {"success": False, "error": "Missing 'command' parameter"}

    timeout = params.get("timeout", 120)

    # Background execution
    if run_in_background:
        return await _run_background(command, timeout, _DEFAULT_DIR)

    # Foreground execution
    return await _run_foreground(command, timeout, stdin_data, _DEFAULT_DIR)


async def _run_foreground(command: str, timeout: int, stdin_data: str,
                          cwd: str) -> dict:
    """Run command and wait for result."""
    try:
        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                shell=True,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        if stdin_data:
            proc.stdin.write(stdin_data.encode())
            await proc.stdin.drain()
            proc.stdin.close()

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        return {
            "success": proc.returncode == 0,
            "data": {
                "stdout": stdout_text,
                "stderr": stderr_text,
                "returncode": proc.returncode,
            },
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _run_background(command: str, timeout: int, cwd: str) -> dict:
    """Start command in background, return immediately with task_id."""
    task_id = str(uuid.uuid4())[:8]

    async def _bg_task():
        try:
            if sys.platform == "win32":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    shell=True,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"Timed out after {timeout}s", "returncode": -1}
        except Exception as e:
            return {"error": str(e), "returncode": -1}

    task = asyncio.create_task(_bg_task())
    _background_tasks[task_id] = task

    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "running",
            "message": f"Command started in background (task_id: {task_id})",
        },
    }


async def check_background(params: dict) -> dict:
    """Check status of a background command.

    params: {task_id: str}
    """
    task_id = params.get("task_id")
    if not task_id:
        # List all tasks
        tasks = {}
        for tid, task in _background_tasks.items():
            tasks[tid] = "completed" if task.done() else "running"
        return {"success": True, "data": {"tasks": tasks}}

    task = _background_tasks.get(task_id)
    if not task:
        return {"success": False, "error": f"Unknown task_id: {task_id}"}

    if task.done():
        result = task.result()
        del _background_tasks[task_id]
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": "completed",
                **result,
            },
        }

    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "running",
        },
    }
