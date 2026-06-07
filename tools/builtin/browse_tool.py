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

    modes_to_try = []

    if params.get("cdp"):
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
        # Try --local --headed first (reuses existing session, visible browser)
        args_local = ["open", url, "--local", "--headed"]
        if session:
            args_local.extend(["--session", session])
        args_local.extend(["--timeout", str(timeout * 1000)])
        modes_to_try.append(args_local)

        # Fallback: --auto-connect (user's Chrome with remote debugging)
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
        # Stop session between attempts (browse CLI leaves stale state on failure)
        await _run_browse("stop", "--session", session or "default", timeout=5)

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


# ===== Human-like Browser Actions =====

async def browse_scroll(params: dict) -> dict:
    """Scroll the page like a human.
    params: {direction: str ("up"|"down"|"left"|"right"), amount?: int (pixels), session?: str}
    """
    direction = params.get("direction", "down")
    amount = params.get("amount", 500)
    session = params.get("session")

    # Map direction to scroll values
    scroll_map = {
        "down": f"window.scrollBy(0, {amount})",
        "up": f"window.scrollBy(0, -{amount})",
        "right": f"window.scrollBy({amount}, 0)",
        "left": f"window.scrollBy(-{amount}, 0)",
    }
    js = scroll_map.get(direction, scroll_map["down"])

    args = ["eval", js]
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_scroll_to(params: dict) -> dict:
    """Scroll to a specific element on the page.
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    js = f"document.querySelector('{selector}').scrollIntoView({{behavior: 'smooth', block: 'center'}})"
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_hover(params: dict) -> dict:
    """Hover over an element (for dropdowns, tooltips, menus).
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    # Use JavaScript to trigger hover events
    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        el.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
        el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
        el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
        return 'Hovered';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_right_click(params: dict) -> dict:
    """Right-click (context menu) on an element.
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        const rect = el.getBoundingClientRect();
        el.dispatchEvent(new MouseEvent('contextmenu', {{
            bubbles: true, cancelable: true,
            clientX: rect.left + rect.width / 2,
            clientY: rect.top + rect.height / 2
        }}));
        return 'Right-clicked';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_double_click(params: dict) -> dict:
    """Double-click on an element.
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        el.dispatchEvent(new MouseEvent('dblclick', {{bubbles: true, cancelable: true}}));
        return 'Double-clicked';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_select(params: dict) -> dict:
    """Select an option from a dropdown.
    params: {selector: str, value: str, session?: str}
    """
    selector = params.get("selector")
    value = params.get("value")
    if not selector or value is None:
        return {"success": False, "error": "Missing 'selector' and/or 'value' parameters"}

    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        el.value = '{value}';
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'Selected: {value}';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_keypress(params: dict) -> dict:
    """Press keyboard keys (Enter, Tab, Escape, arrows, shortcuts).
    params: {keys: str, session?: str}
    keys examples: "Enter", "Tab", "Escape", "ArrowDown", "Ctrl+a", "Ctrl+c", "Ctrl+v"
    """
    keys = params.get("keys")
    if not keys:
        return {"success": False, "error": "Missing 'keys' parameter"}

    # Parse key combinations
    key_parts = keys.split("+")
    modifiers = {"ctrl": false, "shift": false, "alt": false, "meta": false}
    main_key = ""

    for part in key_parts:
        part = part.strip().lower()
        if part in modifiers:
            modifiers[part] = True
        else:
            main_key = part

    # Map common key names
    key_map = {
        "enter": "Enter", "return": "Enter",
        "tab": "Tab",
        "escape": "Escape", "esc": "Escape",
        "space": " ",
        "backspace": "Backspace", "delete": "Delete",
        "up": "ArrowUp", "down": "ArrowDown",
        "left": "ArrowLeft", "right": "ArrowRight",
        "home": "Home", "end": "End",
        "pageup": "PageUp", "pagedown": "PageDown",
    }
    key = key_map.get(main_key, main_key)

    js = f"""
    (() => {{
        const el = document.activeElement || document.body;
        el.dispatchEvent(new KeyboardEvent('keydown', {{
            key: '{key}', code: 'Key{key.upper()}',
            ctrlKey: {str(modifiers["ctrl"]).lower()},
            shiftKey: {str(modifiers["shift"]).lower()},
            altKey: {str(modifiers["alt"]).lower()},
            metaKey: {str(modifiers["meta"]).lower()},
            bubbles: true
        }}));
        el.dispatchEvent(new KeyboardEvent('keyup', {{
            key: '{key}', code: 'Key{key.upper()}',
            ctrlKey: {str(modifiers["ctrl"]).lower()},
            shiftKey: {str(modifiers["shift"]).lower()},
            altKey: {str(modifiers["alt"]).lower()},
            metaKey: {str(modifiers["meta"]).lower()},
            bubbles: true
        }}));
        return 'Pressed: {keys}';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_drag(params: dict) -> dict:
    """Drag an element from one position to another.
    params: {from_selector: str, to_selector: str, session?: str}
    """
    from_sel = params.get("from_selector")
    to_sel = params.get("to_selector")
    if not from_sel or not to_sel:
        return {"success": False, "error": "Missing 'from_selector' and/or 'to_selector'"}

    js = f"""
    (() => {{
        const from = document.querySelector('{from_sel}');
        const to = document.querySelector('{to_sel}');
        if (!from || !to) return 'Element not found';
        const fromRect = from.getBoundingClientRect();
        const toRect = to.getBoundingClientRect();
        from.dispatchEvent(new DragEvent('dragstart', {{
            bubbles: true, clientX: fromRect.left + fromRect.width/2, clientY: fromRect.top + fromRect.height/2
        }}));
        to.dispatchEvent(new DragEvent('drop', {{
            bubbles: true, clientX: toRect.left + toRect.width/2, clientY: toRect.top + toRect.height/2
        }}));
        return 'Dragged';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_focus(params: dict) -> dict:
    """Focus on an element (input, button, etc).
    params: {selector: str, session?: str}
    """
    selector = params.get("selector")
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        el.focus();
        el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
        return 'Focused';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_highlight(params: dict) -> dict:
    """Highlight an element with a red outline (for debugging).
    params: {selector: str, session?: str, duration?: int (ms)}
    """
    selector = params.get("selector")
    duration = params.get("duration", 3000)
    if not selector:
        return {"success": False, "error": "Missing 'selector' parameter"}

    js = f"""
    (() => {{
        const el = document.querySelector('{selector}');
        if (!el) return 'Element not found';
        el.style.outline = '3px solid red';
        el.style.outlineOffset = '2px';
        setTimeout(() => {{ el.style.outline = ''; el.style.outlineOffset = ''; }}, {duration});
        return 'Highlighted';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_get_links(params: dict) -> dict:
    """Get all links on the page.
    params: {session?: str, filter?: str}
    """
    js = """
    (() => {
        const links = Array.from(document.querySelectorAll('a[href]'));
        return links.map(a => ({
            text: a.textContent.trim().substring(0, 100),
            href: a.href
        })).filter(l => l.text && l.href);
    })()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_get_forms(params: dict) -> dict:
    """Get all forms and their inputs on the page.
    params: {session?: str}
    """
    js = """
    (() => {
        const forms = Array.from(document.querySelectorAll('form'));
        return forms.map((form, i) => ({
            index: i,
            action: form.action,
            method: form.method,
            inputs: Array.from(form.querySelectorAll('input, textarea, select')).map(inp => ({
                type: inp.type || inp.tagName.toLowerCase(),
                name: inp.name,
                id: inp.id,
                placeholder: inp.placeholder,
                value: inp.value
            }))
        }));
    })()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_tab(params: dict) -> dict:
    """Switch to a different browser tab.
    params: {index: int, session?: str}
    """
    index = params.get("index", 0)
    js = f"""
    (() => {{
        if ({index} < window.open.length) {{
            // Can't directly switch tabs via JS, but we can try
            return 'Tab switching requires browser chrome API';
        }}
        return 'Tab index out of range';
    }})()
    """
    args = ["eval", js]
    session = params.get("session")
    if session:
        args.extend(["--session", session])

    return await _run_browse(*args, timeout=10)


async def browse_back(params: dict) -> dict:
    """Go back in browser history.
    params: {session?: str}
    """
    args = ["eval", "window.history.back()"]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    return await _run_browse(*args, timeout=10)


async def browse_forward(params: dict) -> dict:
    """Go forward in browser history.
    params: {session?: str}
    """
    args = ["eval", "window.history.forward()"]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    return await _run_browse(*args, timeout=10)


async def browse_refresh(params: dict) -> dict:
    """Refresh the current page.
    params: {session?: str}
    """
    args = ["eval", "window.location.reload()"]
    session = params.get("session")
    if session:
        args.extend(["--session", session])
    return await _run_browse(*args, timeout=10)
