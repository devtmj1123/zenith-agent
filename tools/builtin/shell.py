import asyncio
import re


async def run_command(params: dict) -> dict:
    """Execute shell command.
    params: {command: str, timeout: int=30, _context: str}
    """
    command = params.get("command")

    # If no explicit command, try to extract from LLM context
    if not command:
        context = params.get("_context", "")
        # Look for common patterns: "run: cmd", "command: cmd", code blocks
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

    timeout = params.get("timeout", 30)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "data": {
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
                "returncode": proc.returncode,
            },
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}
