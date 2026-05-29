from __future__ import annotations
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)

# In-memory todo storage
todos: Dict[str, Dict[str, Any]] = {}


class ZenithServer:
    def __init__(self, agent_loop, host: str = "127.0.0.1", port: int = 8765):
        self.agent = agent_loop
        self.host = host
        self.port = port

    async def start(self):
        try:
            from fastapi import FastAPI, WebSocket
            from fastapi.responses import HTMLResponse
            import uvicorn

            app = FastAPI()

            @app.websocket("/ws")
            async def websocket_endpoint(ws: WebSocket):
                await ws.accept()
                session_id = f"ws_{id(ws)}"
                try:
                    while True:
                        data = await ws.receive_text()
                        msg = json.loads(data)
                        goal = msg.get("content", "")

                        if not goal:
                            continue

                        # Run agent
                        def on_event(event):
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    ws.send_text(json.dumps({
                                        "type": event.type.value,
                                        "content": event.content,
                                        "metadata": event.metadata,
                                    })),
                                    asyncio.get_event_loop()
                                )
                            except Exception:
                                pass

                        result = await self.agent.run(goal, session_id)
                        await ws.send_text(json.dumps({
                            "type": "done",
                            "content": result.final_response,
                        }))
                except Exception as e:
                    log.error("WebSocket error: %s", e)

            @app.post("/chat")
            async def chat_endpoint(request: dict):
                goal = request.get("content", "")
                result = await self.agent.run(goal)
                return {"response": result.final_response}

            @app.get("/health")
            async def health():
                return {"status": "ok", "timestamp": datetime.now().isoformat()}

            # ── Todo API ──────────────────────────────────────────────

            @app.get("/todos", response_model=List[Dict[str, Any]])
            async def list_todos(completed: Optional[bool] = None):
                """List all todos, optionally filtered by completion status."""
                items = list(todos.values())
                if completed is not None:
                    items = [t for t in items if t["completed"] == completed]
                return items

            @app.post("/todos", response_model=Dict[str, Any], status_code=201)
            async def create_todo(request: dict):
                """Create a new todo. Requires 'title'; 'description' and 'completed' are optional."""
                title = request.get("title", "").strip()
                if not title:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=422, detail="Title is required")
                todo_id = str(uuid.uuid4())[:8]
                todo = {
                    "id": todo_id,
                    "title": title,
                    "description": request.get("description", ""),
                    "completed": request.get("completed", False),
                }
                todos[todo_id] = todo
                return todo

            @app.get("/todos/{todo_id}", response_model=Dict[str, Any])
            async def get_todo(todo_id: str):
                """Get a single todo by ID."""
                from fastapi import HTTPException
                if todo_id not in todos:
                    raise HTTPException(status_code=404, detail="Todo not found")
                return todos[todo_id]

            @app.patch("/todos/{todo_id}", response_model=Dict[str, Any])
            async def update_todo(todo_id: str, request: dict):
                """Update a todo. Pass any fields to change (title, description, completed)."""
                from fastapi import HTTPException
                if todo_id not in todos:
                    raise HTTPException(status_code=404, detail="Todo not found")
                todo = todos[todo_id]
                if "title" in request:
                    todo["title"] = request["title"]
                if "description" in request:
                    todo["description"] = request["description"]
                if "completed" in request:
                    todo["completed"] = request["completed"]
                return todo

            @app.delete("/todos/{todo_id}", status_code=204)
            async def delete_todo(todo_id: str):
                """Delete a todo by ID."""
                from fastapi import HTTPException
                if todo_id not in todos:
                    raise HTTPException(status_code=404, detail="Todo not found")
                del todos[todo_id]

            # ── End Todo API ──────────────────────────────────────────

            config = uvicorn.Config(app, host=self.host, port=self.port)
            server = uvicorn.Server(config)
            await server.serve()

        except ImportError:
            log.error("FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
            raise
