---
name: coding
description: Use when writing code, fixing bugs, building software, creating apps, web development, frontend, UI components, running commands, editing files, or any programming and development task
---

# Coding Rules

## Non-Interactive Commands

CLI tools that prompt for input will hang the shell tool. Use `--yes`, `-y`, or the non-interactive variant. If a command times out, it's probably interactive.

## Error Recovery

- NEVER retry the exact same command that just failed.
- After 3 failures, stop and report what went wrong.

## Working Directory

- Shell tool working directory is the Zenith project root, not the desktop.
- Use `cd C:\path && command` to run in a specific directory.
