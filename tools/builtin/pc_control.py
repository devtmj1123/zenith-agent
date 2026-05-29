"""PC Control — Windows UIA desktop automation via pywinauto.

Provides: get_windows, get_ui_tree, click, fill, press, screenshot, launch, focus.
Each tool uses pywinauto's UIA backend for reliable Windows automation.
"""
from __future__ import annotations
import asyncio
import json
import os
import subprocess
import time
from typing import Optional


def _get_backend():
    """Get pywinauto UIA backend."""
    try:
        from pywinauto import Desktop
        return Desktop(backend="uia")
    except Exception as e:
        return None


async def pc_get_windows(params: dict) -> dict:
    """List all visible windows with title, class, and rect.

    params: {filter?: str}
    """
    def _do():
        desktop = _get_backend()
        if not desktop:
            return {"success": False, "error": "Failed to initialize UIA backend"}

        windows = []
        for win in desktop.windows():
            try:
                if not win.is_visible():
                    continue
                title = win.window_text()
                if not title:
                    continue
                # Filter by title if provided
                filt = params.get("filter", "")
                if filt and filt.lower() not in title.lower():
                    continue
                rect = win.rectangle()
                windows.append({
                    "title": title,
                    "class_name": win.class_name(),
                    "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
                    "handle": win.handle,
                })
            except Exception:
                continue
        return {"success": True, "data": {"windows": windows, "count": len(windows)}}

    return await asyncio.to_thread(_do)


async def pc_get_ui_tree(params: dict) -> dict:
    """Get accessibility tree of a window or control.

    params: {title?: str, handle?: int, depth?: int, control_type?: str}
    """
    def _do():
        desktop = _get_backend()
        if not desktop:
            return {"success": False, "error": "Failed to initialize UIA backend"}

        title = params.get("title")
        handle = params.get("handle")
        depth = params.get("depth", 3)
        control_type = params.get("control_type")

        try:
            if handle:
                win = desktop.window(handle=handle)
            elif title:
                wins = desktop.windows(title=title)
                if not wins:
                    return {"success": False, "error": f"No window found with title: {title}"}
                win = wins[0]
            else:
                # Return list of top-level windows
                windows = []
                for w in desktop.windows():
                    try:
                        if w.is_visible():
                            windows.append({
                                "title": w.window_text(),
                                "handle": w.handle,
                            })
                    except Exception:
                        continue
                return {"success": True, "data": {"windows": windows}}

            # Build UI tree
            def _build_tree(ctrl, current_depth, max_depth):
                if current_depth > max_depth:
                    return None
                try:
                    info = {
                        "control_type": ctrl.element_info.control_type or "Unknown",
                        "title": ctrl.window_text() or "",
                        "class_name": ctrl.element_info.class_name or "",
                        "rect": None,
                    }
                    try:
                        rect = ctrl.rectangle()
                        info["rect"] = {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
                    except Exception:
                        pass

                    # Filter by control type if provided
                    if control_type and info["control_type"].lower() != control_type.lower():
                        return None

                    children = []
                    if current_depth < max_depth:
                        try:
                            for child in ctrl.children():
                                child_info = _build_tree(child, current_depth + 1, max_depth)
                                if child_info:
                                    children.append(child_info)
                        except Exception:
                            pass

                    if children:
                        info["children"] = children
                    return info
                except Exception:
                    return None

            tree = _build_tree(win, 0, depth)
            return {"success": True, "data": {"tree": tree, "title": win.window_text()}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_click(params: dict) -> dict:
    """Click a UI element by title, control_type, or coordinates.

    params: {title?: str, control_type?: str, x?: int, y?: int, button?: str, double?: bool}
    """
    def _do():
        desktop = _get_backend()
        if not desktop:
            return {"success": False, "error": "Failed to initialize UIA backend"}

        x = params.get("x")
        y = params.get("y")
        title = params.get("title")
        control_type = params.get("control_type")
        button = params.get("button", "left")
        double = params.get("double", False)

        try:
            if x is not None and y is not None:
                # Coordinate click
                import pyautogui
                if double:
                    pyautogui.doubleClick(x, y)
                else:
                    pyautogui.click(x, y, button=button)
                return {"success": True, "data": {"action": "click", "x": x, "y": y}}

            if title:
                # Find and click by title
                for win in desktop.windows():
                    try:
                        if title.lower() in win.window_text().lower():
                            win.click_input()
                            return {"success": True, "data": {"action": "click", "title": win.window_text()}}
                    except Exception:
                        continue
                return {"success": False, "error": f"No element found with title: {title}"}

            return {"success": False, "error": "Provide title or x,y coordinates"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_fill(params: dict) -> dict:
    """Type text into a UI element or at current cursor.

    params: {text: str, title?: str, press_enter?: bool, clear_first?: bool}
    """
    def _do():
        text = params.get("text")
        if not text:
            return {"success": False, "error": "Missing 'text' parameter"}

        title = params.get("title")
        press_enter = params.get("press_enter", False)
        clear_first = params.get("clear_first", False)

        try:
            if title:
                desktop = _get_backend()
                if not desktop:
                    return {"success": False, "error": "Failed to initialize UIA backend"}

                for win in desktop.windows():
                    try:
                        if title.lower() in win.window_text().lower():
                            if clear_first:
                                win.type_keys("^a", with_spaces=True)
                            win.type_keys(text, with_spaces=True)
                            if press_enter:
                                win.type_keys("{ENTER}")
                            return {"success": True, "data": {"action": "fill", "title": win.window_text()}}
                    except Exception:
                        continue
                return {"success": False, "error": f"No element found with title: {title}"}
            else:
                # Type at current cursor position
                import pyautogui
                if clear_first:
                    pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(text, interval=0.02)
                if press_enter:
                    pyautogui.press("enter")
                return {"success": True, "data": {"action": "fill", "text": text}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_press(params: dict) -> dict:
    """Press keyboard keys.

    params: {keys: str} — e.g. "enter", "ctrl+c", "alt+tab", "f5"
    """
    def _do():
        keys = params.get("keys")
        if not keys:
            return {"success": False, "error": "Missing 'keys' parameter"}

        try:
            import pyautogui
            parts = [k.strip().lower() for k in keys.split("+")]
            if len(parts) == 1:
                pyautogui.press(parts[0])
            else:
                pyautogui.hotkey(*parts)
            return {"success": True, "data": {"action": "press", "keys": keys}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_screenshot(params: dict) -> dict:
    """Take a screenshot of the screen or a specific window.

    params: {title?: str, save_path?: str}
    """
    def _do():
        save_path = params.get("save_path", "screenshot.png")
        title = params.get("title")

        try:
            if title:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")
                for win in desktop.windows():
                    try:
                        if title.lower() in win.window_text().lower():
                            img = win.capture_as_image()
                            img.save(save_path)
                            return {"success": True, "data": {"path": save_path, "title": win.window_text()}}
                    except Exception:
                        continue
                return {"success": False, "error": f"No window found with title: {title}"}
            else:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(save_path)
                return {"success": True, "data": {"path": save_path}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_launch(params: dict) -> dict:
    """Launch an application.

    params: {app: str, args?: str, wait?: bool}
    """
    def _do():
        app = params.get("app")
        if not app:
            return {"success": False, "error": "Missing 'app' parameter"}

        args = params.get("args", "")
        wait = params.get("wait", False)

        try:
            cmd = f"{app} {args}".strip()
            if wait:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return {
                    "success": result.returncode == 0,
                    "data": {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
                }
            else:
                subprocess.Popen(cmd, shell=True)
                return {"success": True, "data": {"action": "launch", "app": app}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)


async def pc_focus(params: dict) -> dict:
    """Bring a window to focus.

    params: {title: str}
    """
    def _do():
        title = params.get("title")
        if not title:
            return {"success": False, "error": "Missing 'title' parameter"}

        try:
            desktop = _get_backend()
            if not desktop:
                return {"success": False, "error": "Failed to initialize UIA backend"}

            for win in desktop.windows():
                try:
                    if title.lower() in win.window_text().lower():
                        win.set_focus()
                        return {"success": True, "data": {"action": "focus", "title": win.window_text()}}
                except Exception:
                    continue
            return {"success": False, "error": f"No window found with title: {title}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    return await asyncio.to_thread(_do)
