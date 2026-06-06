"""Zenith-OS Web Server — Flask backend with WebSocket support.

Serves the neumorphism UI and bridges to the Zenith agent loop.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sock import Sock

# Add parent directory to path for Zenith imports
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

log = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"))
app.config['SECRET_KEY'] = os.urandom(24).hex()

sock = Sock(app)

# Global agent instance (initialized on startup)
_agent = None
_agent_loop = None
_settings = None


def get_agent():
    """Get or create the Zenith agent."""
    global _agent, _agent_loop, _settings
    if _agent is None:
        from config.settings import Settings
        from main import build_agent

        _settings = Settings()
        _settings.load_from_env()

        def on_event(event):
            """Forward agent events to WebSocket clients."""
            # Events are handled by the WebSocket connection
            pass

        _agent = build_agent(_settings, on_event=on_event)
    return _agent


def run_async(coro):
    """Run async function in a new thread with its own event loop."""
    result = None
    error = None

    def _run():
        nonlocal result, error
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
        except Exception as e:
            error = e
        finally:
            loop.close()

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join(timeout=120)  # 2 minute timeout

    if error:
        raise error
    return result


# ===== Routes =====

@app.route('/')
def index():
    """Serve the main UI."""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    return send_from_directory(app.static_folder, filename)


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """HTTP fallback for chat."""
    data = request.json
    message = data.get('message', '')

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        agent = get_agent()
        state = run_async(agent.run(message, session_id="web"))
        return jsonify({
            'response': state.final_response,
            'tool_calls': state.tool_calls_made,
            'tokens_used': state.tokens_used
        })
    except Exception as e:
        log.error(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/research', methods=['POST'])
def api_research():
    """Start a research task."""
    data = request.json
    query = data.get('query', '')
    domain = data.get('domain', 'auto')

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        agent = get_agent()
        prompt = f"Research the following topic: {query}"
        if domain != 'auto':
            prompt += f" (domain: {domain})"

        state = run_async(agent.run(prompt, session_id="research"))
        return jsonify({
            'response': state.final_response,
            'tool_calls': state.tool_calls_made,
            'tokens_used': state.tokens_used
        })
    except Exception as e:
        log.error(f"Research error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/stats')
def api_memory_stats():
    """Get memory statistics."""
    try:
        agent = get_agent()
        desire_stats = agent.desire_engine.get_stats()
        assoc_stats = agent.association_engine.get_stats()

        return jsonify({
            'total_memories': 0,  # Would need to query soft memory
            'active_desires': desire_stats['active_desires'],
            'total_associations': assoc_stats['total_associations'],
            'dream_ready': desire_stats['dream_ready']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/list')
def api_memory_list():
    """List recent memories."""
    try:
        # Would need to query soft memory
        return jsonify({'memories': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tools')
def api_tools():
    """List available tools."""
    try:
        agent = get_agent()
        tools = agent._tools_schema
        return jsonify({'tools': tools})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dream/stats')
def api_dream_stats():
    """Get dream controller statistics."""
    try:
        agent = get_agent()
        stats = agent.dream_controller.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dream/start', methods=['POST'])
def api_dream_start():
    """Start a dream cycle."""
    try:
        agent = get_agent()
        result = run_async(agent.dream_controller.dream())
        return jsonify({
            'desires_pursued': result.desires_pursued,
            'associations_found': result.associations_found,
            'hypotheses_generated': result.hypotheses_generated,
            'novel_insights': result.novel_insights,
            'duration_seconds': result.duration_seconds
        })
    except Exception as e:
        log.error(f"Dream error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['POST'])
def api_settings():
    """Update settings."""
    data = request.json
    # Would save to settings file
    return jsonify({'status': 'ok'})


# ===== WebSocket =====

@sock.route('/ws')
def websocket(ws):
    """WebSocket connection for real-time chat."""
    agent = get_agent()
    session_id = f"ws_{id(ws)}"

    # Set up event forwarding
    events = []

    def on_event(event):
        events.append(event)

    agent.on_event = on_event

    try:
        while True:
            data = ws.receive()
            if not data:
                break

            message = json.loads(data)
            msg_type = message.get('type')

            if msg_type == 'chat':
                content = message.get('content', '')
                if not content:
                    continue

                # Run agent in background thread
                def run_chat():
                    try:
                        state = run_async(agent.run(content, session_id=session_id))
                        ws.send(json.dumps({
                            'type': 'chat_response',
                            'content': state.final_response,
                            'tool_calls': state.tool_calls_made,
                            'tokens_used': state.tokens_used
                        }))
                    except Exception as e:
                        ws.send(json.dumps({
                            'type': 'error',
                            'content': str(e)
                        }))

                thread = threading.Thread(target=run_chat)
                thread.start()

                # Send events while running
                while thread.is_alive():
                    while events:
                        event = events.pop(0)
                        ws.send(json.dumps({
                            'type': event.type.value if hasattr(event.type, 'value') else str(event.type),
                            'content': event.content
                        }))
                    import time
                    time.sleep(0.1)

                # Send remaining events
                while events:
                    event = events.pop(0)
                    ws.send(json.dumps({
                        'type': event.type.value if hasattr(event.type, 'value') else str(event.type),
                        'content': event.content
                    }))

            elif msg_type == 'research':
                query = message.get('query', '')
                domain = message.get('domain', 'auto')

                def run_research():
                    try:
                        prompt = f"Research: {query}"
                        if domain != 'auto':
                            prompt += f" (domain: {domain})"
                        state = run_async(agent.run(prompt, session_id="research"))
                        ws.send(json.dumps({
                            'type': 'research_result',
                            'content': {
                                'response': state.final_response,
                                'tool_calls': state.tool_calls_made
                            }
                        }))
                    except Exception as e:
                        ws.send(json.dumps({
                            'type': 'error',
                            'content': str(e)
                        }))

                threading.Thread(target=run_research).start()

            elif msg_type == 'dream':
                def run_dream():
                    try:
                        result = run_async(agent.dream_controller.dream())
                        ws.send(json.dumps({
                            'type': 'dream_result',
                            'content': {
                                'desires_pursued': result.desires_pursued,
                                'associations_found': result.associations_found,
                                'novel_insights': result.novel_insights,
                                'duration_seconds': result.duration_seconds
                            }
                        }))
                    except Exception as e:
                        ws.send(json.dumps({
                            'type': 'error',
                            'content': str(e)
                        }))

                threading.Thread(target=run_dream).start()

    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        log.info(f"WebSocket connection closed: {session_id}")


# ===== Main =====

def main():
    """Start the Zenith-OS server."""
    import argparse

    parser = argparse.ArgumentParser(description="Zenith-OS Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"\n  Zenith-OS Server")
    print(f"  ===============")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
