"""Browse.sh adapter — wraps the browse CLI for browser automation.

Provides: open, snapshot, click, fill, get, screenshot, skills, eval, wait.
Each tool runs `browse <cmd>` via subprocess and returns structured output.
"""
from __future__ import annotations
import asyncio
import json
import shutil
from typing import Optional


async def _run_browse(*args: str, timeout: int = 30) -> dict:
    """Run a browse CLI command and return parsed output."""
    browse_bin = shutil.which("browse")
    if not browse_bin:
        # Windows: try .cmd extension
        import os
        npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm", "browse.cmd")
        if os.path.exists(npm_global):
            browse_bin = npm_global
        else:
            return {"success": False, "error": "browse CLI not installed. Run: npm install -g browse"}

    cmd = [browse_bin, *args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            return {"success": False, "error": stderr_text or f"Exit code {proc.returncode}", "stdout": stdout_text}

        # Try JSON parse
        try:
            data = json.loads(stdout_text)
            return {"success": True, "data": data}
        except json.JSONDecodeError:
            return {"success": True, "data": {"output": stdout_text}}

    except asyncio.TimeoutError:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browse_open(params: dict) -> dict:
    """Open a URL in a browser session.
    params: {url: str, session?: str, headless?: bool, timeout?: int, auto_connect?: bool, cdp?: str}
    """
    url = params.get("url")
    if not url:
        return {"success": False, "error": "Missing 'url' parameter"}

    timeout = params.get("timeout", 30)
    session = params.get("session")

    # Strategy: try --local first (most reliable), fall back to --auto-connect
    # --local launches its own browser instance (no remote debugging needed)
    # --auto-connect tries to find existing Chrome with remote debugging
    modes_to_try = []

    if params.get("cdp"):
        # Explicit CDP URL/port provided
        args = ["open", url, "--cdp", params["cdp"]]
        if session:
            args.extend(["--session", session])
        args.extend(["--timeout", str(timeout * 1000)])
        modes_to_try.append(args)
    elif params.get("headless"):
        args = ["open", url, "--local", "--headless"]
        if session:
            args.extend(["--session", session])
        args.extend(["--timeout", str(timeout * 1000)])
        modes_to_try.append(args)
    else:
        # Try --local first (launches own browser, most reliable)
        args_local = ["open", url, "--local"]
        if session:
            args_local.extend(["--session", session])
        args_local.extend(["--timeout", str(timeout * 1000)])
        modes_to_try.append(args_local)

        # Fallback: --auto-connect (needs Chrome with --remote-debugging-port)
        args_auto = ["open", url, "--auto-connect"]
        if session:
            args_auto.extend(["--session", session])
        args_auto.extend(["--timeout", str(timeout * 1000)])
        modes_to_try.append(args_auto)

    result = None
    for args in modes_to_try:
        result = await _run_browse(*args, timeout=timeout + 5)
        if result["success"]:
            break
        # If session conflict, stop and retry
        if "already running" in str(result.get("error", "")):
            await _run_browse("stop", "--session", session or "default", timeout=10)
            result = await _run_browse(*args, timeout=timeout + 5)
            if result["success"]:
                break

    if result and result["success"]:
        # Auto-snapshot after open for immediate element access
        snap_args = ["snapshot", "--compact"]
        if session:
            snap_args.extend(["--session", session])
        snap_result = await _run_browse(*snap_args, timeout=15)
        if snap_result["success"]:
            snap_data = snap_result["data"]
            result["data"]["snapshot"] = snap_data.get("output", "") if isinstance(snap_data, dict) else str(snap_data)

    return result or {"success": False, "error": "All browser modes failed"}


async def browse_snapshot(params: dict) -> dict:
    """Get accessibility snapshot of the active page (cached refs for click/fill).
    params: {session?: str, filter?: str, max_depth?: int}
    """
    args = ["snapshot", "--compact"]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    filt = params.get("filter")
    if filt:
        args.extend(["--filter", filt])
    max_depth = params.get("max_depth")
    if max_depth:
        args.extend(["--max-depth", str(max_depth)])

    return await _run_browse(*args, timeout=15)


async def browse_click(params: dict) -> dict:
    """Click an element by snapshot ref, XPath, or selector.
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    args = ["click", selector]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=15)


async def browse_fill(params: dict) -> dict:
    """Fill an input element by snapshot ref, XPath, or selector.
    params: {selector: str, value: str, session?: str, press_enter?: bool}
    """
    selector = params.get("selector")
    value = params.get("value")
    if not selector or value is None:
        return {"success": False, "error": "Missing 'selector' and/or 'value' parameters"}

    args = ["fill", selector, value]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    if params.get("press_enter"):
        args.append("--press-enter")

    return await _run_browse(*args, timeout=15)


async def browse_get(params: dict) -> dict:
    """Read page data: url, title, text, html, markdown, value, visible, checked.
    params: {what: str, selector?: str, session?: str}
    """
    what = params.get("what", "text")
    args = ["get", what]
    selector = params.get("selector")
    if selector:
        args.append(selector)
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=15)


async def browse_screenshot(params: dict) -> dict:
    """Take a screenshot of the active page.
    params: {session?: str}
    """
    args = ["screenshot"]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=15)


async def browse_skills(params: dict) -> dict:
    """Search browse.sh skill catalog for pre-built browser automation playbooks.
    params: {query?: str, limit?: int}
    """
    query = params.get("query")
    limit = params.get("limit", 10)

    if query:
        args = ["skills", "find", query, "--json", "--limit", str(limit)]
    else:
        args = ["skills", "list", "--json", "--limit", str(limit)]

    return await _run_browse(*args, timeout=15)


async def browse_eval(params: dict) -> dict:
    """Evaluate JavaScript in the active browser page.
    params: {expression: str, session?: str}
    """
    expression = params.get("expression")
    if not expression:
        return {"success": False, "error": "Missing 'expression' parameter"}

    args = ["eval", expression]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=15)


async def browse_wait(params: dict) -> dict:
    """Wait for a load state, selector state, or timeout.
    params: {selector_or_state: str, session?: str, timeout?: int}
    """
    selector_or_state = params.get("selector_or_state")
    if not selector_or_state:
        return {"success": False, "error": "Missing 'selector_or_state' parameter"}

    args = ["wait", selector_or_state]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    timeout = params.get("timeout", 10)
    args.extend(["--timeout", str(timeout * 1000)])

    return await _run_browse(*args, timeout=timeout + 5)
