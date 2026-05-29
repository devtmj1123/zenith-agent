---
name: creating-tools
description: Use when a tool is not found, a tool call returns "not registered" error, or when repeating the same shell commands that could be a dedicated tool
---

# Creating Tools

## When to Create

- Tool not found error — create it instead of skipping
- Repeating the same shell commands — turn into a tool
- Need a capability built-in tools don't cover

## How to Create

Call `create_tool` with `name`, `description`, `code`, and `parameters`.

Code must define a class extending `BaseDynamicTool`:

```python
from dynamic_tools.base_tool import BaseDynamicTool, DynamicToolResult

class MyTool(BaseDynamicTool):
    name = "tool_name"
    description = "What it does"
    parameters = {"type": "object", "properties": {...}, "required": [...]}

    async def execute(self, params: dict) -> DynamicToolResult:
        result = do_something(params["key"])
        return DynamicToolResult(True, data=result)
```

## Rules

- One tool, one purpose
- 5-second timeout — keep execution fast
- Cannot override built-in tool names
- Use `run_command` for shell ops instead of reimplementing
- After creating, verify it works by calling it
