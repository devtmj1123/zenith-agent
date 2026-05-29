---
name: pc-control
description: Use when controlling desktop applications, clicking buttons, filling forms, taking screenshots, launching apps, or automating any Windows GUI workflow
---

# PC Control

## Tools

`pc_get_windows`, `pc_get_ui_tree`, `pc_click`, `pc_fill`, `pc_press`, `pc_screenshot`, `pc_launch`, `pc_focus`

## When to Use PC Control vs Browser

- Controlling desktop apps (Notepad, Excel, etc.) → use PC control tools
- Controlling web pages → use browser tools instead

## Workflow

1. `pc_get_windows` — find the target window by title
2. `pc_get_ui_tree` — read the UI structure, get element info
3. `pc_click` or `pc_fill` — interact with elements
4. `pc_get_windows` or `pc_screenshot` — verify the action worked

## Rules

- Always get the UI tree before clicking or filling — understand the structure first
- Use window title filter to find specific windows
- For filling: set `press_enter: true` to submit after typing
- After each action, verify by checking window state or taking a screenshot
- Use `pc_launch` to start applications before interacting with them

## Auto-Connect

- Default behavior uses UIA backend (Windows accessibility)
- Use coordinates (x, y) when element title is not available

## Response Style

- Keep responses brief — state what was done and what the user can do next
- Never include raw UI tree data in responses
