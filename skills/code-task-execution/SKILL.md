---
name: code-task-execution
description: Use when writing code, fixing bugs, building apps, running commands, editing files, or any programming and development task
---

# Code Task Execution

## Tools

`run_command`, `read_file`, `write_file`, `edit_file`, `list_dir`, `glob_search`, `grep_search`

## Requirements

- When the request is clear, execute immediately — never ask "which direction" or "what would you prefer."
- Pick a reasonable default when uncertain. The user will correct you if needed.
- Never ask "What would you like me to help with?" — the user already told you.
- Never read files to "understand the project" unless the task requires modifying existing code.
- If the task says "create" or "build", just create it — don't explore first.

## Execution

- Always use `write_file` or `edit_file` to create/modify files. Never output code as text in your response.
- Use `edit_file` for small changes to existing files. Use `write_file` only for new files or full rewrites.
- Search first (grep_search) to locate existing code, then read the specific match.
- If the search didn't find it, try different keywords.
- Use non-interactive flags (`--yes`, `-y`) for CLI tools.
- After each step, verify the result. Try a different approach if it failed.
- Do not re-read files you just wrote. You already know their content.

## Error Fixing

- Read the error message — it usually says what's wrong.
- Fix the root cause. If a dependency is missing, install it.
- After fixing, verify the fix worked.
- After 3 failures, stop and report what you tried.

## Best Practices
- After every file change, verify it works — run the app, run tests, check the output.
- Explore the project structure before writing code — understand existing patterns, dependencies, and conventions first.
- Measure success with evidence — command output, test results, browser state. "It probably works" is not success.
- Monitor context size — if reading many files, stop and ask what's actually needed. Large context degrades reasoning.
- Use git — commit after each working change. Never lose progress to a failed experiment.

## Response Style
- Keep responses brief — summarize what was done in 1-3 sentences.
- Never include tables, tool output, or raw data in responses.
- State the result, not the process. "Created the app" not "First I ran write_file, then I ran run_command..."
- If TTS is enabled, write responses as natural speech — no markdown formatting, no special characters.

## Project Location

- Check if CWD is appropriate before creating a project.
- If CWD is a system/tool directory, ask the user where they want the project.
