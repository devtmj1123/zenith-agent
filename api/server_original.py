from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


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
                return {"status": "ok", "version": "1.0"}

            config = uvicorn.Config(app, host=self.host, port=self.port)
            server = uvicorn.Server(config)
            await server.serve()

        except ImportError:
            log.error("FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
            raise
