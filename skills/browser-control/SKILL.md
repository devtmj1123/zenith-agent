---
name: browser-control
description: Use when opening websites, navigating pages, filling forms, clicking buttons, searching within a site, watching videos, or automating any browser workflow
---

# Browser Control

## Tools

`browse_open`, `browse_snapshot`, `browse_click`, `browse_fill`, `browse_get`, `browse_screenshot`, `browse_eval`, `browse_wait`

## When to Use Browser vs Search

- Opening a website and interacting with it → use browser tools
- Finding information from the web → use `search` tool instead

## Workflow

1. `browse_open` — navigate to the target URL (launches local browser automatically)
2. `browse_snapshot` — read page structure, get element refs
3. `browse_fill` or `browse_click` — interact using refs from snapshot
4. `browse_snapshot` again after each navigation or page change

## Rules

- **Always snapshot before clicking or filling** — refs change after navigation
- Use the exact ref string from snapshot output as the selector (e.g. `[3-7429]`)
- For filling: set `press_enter: true` to submit after typing
- For clicking: verify the action worked by snapshotting the new page state
- After each action, snapshot or get the page title/url to confirm

## Error Recovery

- "No active page" → call `browse_open` first to launch browser
- "Session already running" → `browse_open` handles this automatically (stops and retries)
- "No debuggable browser" → `browse_open` now uses `--local` mode by default (launches own browser)
- If refs are stale → take a fresh `browse_snapshot` to get current refs

## Auto-Connect vs Local

- **Default**: uses `--local` mode (launches its own browser, most reliable)
- **Auto-connect**: tries to attach to existing Chrome with remote debugging
- Use `cdp` param to specify a custom CDP URL/port
- Use `headless: true` for background automation (no visible window)

## Response Style

- Keep responses brief — state what was done and what the user can do next
- Never include raw page data, JSON, or element refs in responses
