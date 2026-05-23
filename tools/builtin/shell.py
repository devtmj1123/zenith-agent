import asyncio


async def run_command(params: dict) -> dict:
    """Execute shell command.
    params: {command: str, timeout: int=30}
    """
    command = params.get("command")
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
