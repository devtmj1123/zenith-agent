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
import time
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
_settings = None
_agent_ready = False
_agent_status = "loading"
_connected_ws_clients = set()  # Track connected WebSocket clients for notifications


def get_agent():
    """Get or create the Zenith agent."""
    global _agent, _settings, _agent_ready, _agent_status
    if _agent is None:
        try:
            _agent_status = "loading_model"
            from config.settings import Settings
            from main import build_agent

            _settings = Settings()
            _settings.load_from_env()

            _agent_status = "initializing_agent"
            _agent = build_agent(_settings, on_event=lambda e: None)
            _agent_ready = True
            _agent_status = "ready"
        except Exception as e:
            _agent_status = f"error: {str(e)[:100]}"
            raise
    return _agent


def run_async(coro):
    """Run async function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===== Reminder Notifications =====
def _start_reminder_notifier():
    """Start background thread that checks for due reminders and notifies WebSocket clients."""
    def _notifier_loop():
        # Import here to avoid circular imports
        time.sleep(5)  # Wait for server to start
        try:
            from tools.builtin.reminders_tool import on_reminder_due
            def _on_due(reminder):
                notification = {
                    'type': 'reminder',
                    'content': {
                        'title': reminder.get('title', 'Reminder'),
                        'description': reminder.get('description', ''),
                        'datetime': reminder.get('datetime', ''),
                        'id': reminder.get('id', ''),
                    }
                }
                # Send to all connected clients
                dead_clients = set()
                for ws in list(_connected_ws_clients):
                    try:
                        ws.send(json.dumps(notification))
                    except Exception:
                        dead_clients.add(ws)
                _connected_ws_clients.difference_update(dead_clients)

            on_reminder_due(_on_due)
            log.info("Reminder notification system started")
        except Exception as e:
            log.warning(f"Could not start reminder notifier: {e}")

    t = threading.Thread(target=_notifier_loop, daemon=True)
    t.start()


# Start reminder notifier
_start_reminder_notifier()


# ===== Routes =====

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Check if agent is ready."""
    return jsonify({
        'ready': _agent_ready,
        'status': _agent_status,
    })


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """HTTP chat endpoint."""
    data = request.json
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        agent = get_agent()
        state = run_async(agent.run(message, session_id="web"))
        return jsonify({
            'response': state.final_response or '',
            'tool_calls': state.tool_calls_made,
            'tokens_used': state.tokens_used
        })
    except Exception as e:
        log.error(f"Chat error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/research', methods=['POST'])
def api_research():
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
            'response': state.final_response or '',
            'tool_calls': state.tool_calls_made,
            'tokens_used': state.tokens_used
        })
    except Exception as e:
        log.error(f"Research error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/stats')
def api_memory_stats():
    try:
        agent = get_agent()
        desire_stats = agent.desire_engine.get_stats()
        assoc_stats = agent.association_engine.get_stats()
        return jsonify({
            'total_memories': 0,
            'active_desires': desire_stats['active_desires'],
            'total_associations': assoc_stats['total_associations'],
            'dream_ready': desire_stats['dream_ready']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/list')
def api_memory_list():
    return jsonify({'memories': []})


@app.route('/api/tools')
def api_tools():
    try:
        agent = get_agent()
        return jsonify({'tools': agent._tools_schema})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dream/stats')
def api_dream_stats():
    try:
        agent = get_agent()
        stats = agent.dream_controller.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dream/start', methods=['POST'])
def api_dream_start():
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
        log.error(f"Dream error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['POST'])
def api_settings():
    data = request.json
    return jsonify({'status': 'ok'})


@app.route('/api/diagnosis')
def api_diagnosis():
    """Run self-diagnosis."""
    try:
        from core.self_diagnosis import run_diagnosis
        result = run_diagnosis()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/diagnosis/fix', methods=['POST'])
def api_diagnosis_fix():
    """Run auto-fix for diagnosed issues."""
    try:
        from core.self_diagnosis import run_auto_fix
        result = run_auto_fix()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reminders')
def api_reminders():
    """List all pending reminders."""
    try:
        from tools.builtin.reminders_tool import reminders
        result = run_async(reminders({"action": "list"}))
        return jsonify(result)
    except Exception as e:
        return jsonify({"reminders": [], "error": str(e)})


@app.route('/api/reminders/create', methods=['POST'])
def api_create_reminder():
    """Create a new reminder."""
    try:
        data = request.json or {}
        from tools.builtin.reminders_tool import reminders
        args = {
            "action": "create",
            "title": data.get("title", ""),
            "datetime": data.get("datetime", ""),
            "description": data.get("description", ""),
        }
        result = run_async(reminders(args))
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/reminders/dismiss', methods=['POST'])
def api_dismiss_reminder():
    """Dismiss a reminder."""
    try:
        data = request.json or {}
        from tools.builtin.reminders_tool import reminders
        result = run_async(reminders({"action": "dismiss", "reminder_id": data.get("reminder_id", "")}))
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    """Run auto-fix."""
    try:
        from core.self_diagnosis import run_auto_fix
        result = run_auto_fix()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== WebSocket =====

@sock.route('/ws')
def websocket(ws):
    """WebSocket for real-time chat.

    IMPORTANT: flask-sock is synchronous. All work must happen in this thread.
    """
    # Register client for notifications
    _connected_ws_clients.add(ws)

    # Try to get agent, handle failure gracefully
    try:
        agent = get_agent()
    except Exception as e:
        log.error(f"Agent init failed: {e}")
        ws.send(json.dumps({
            'type': 'error',
            'content': f'Agent initialization failed: {str(e)[:200]}'
        }))
        # Keep connection alive so frontend can retry
        while True:
            data = ws.receive()
            if not data:
                break
            msg = json.loads(data) if data else {}
            if msg.get('type') == 'ping':
                ws.send(json.dumps({'type': 'pong'}))
            elif msg.get('type') == 'status_request':
                ws.send(json.dumps({'type': 'status', 'ready': False, 'error': str(e)[:200]}))
        _connected_ws_clients.discard(ws)
        return

    session_id = f"ws_{id(ws)}"

    try:
        while True:
            data = ws.receive()
            if not data:
                break

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                ws.send(json.dumps({'type': 'error', 'content': 'Invalid JSON'}))
                continue

            msg_type = message.get('type')

            if msg_type == 'ping':
                ws.send(json.dumps({'type': 'pong'}))
                continue

            if msg_type == 'chat':
                content = message.get('content', '')
                if not content:
                    continue

                try:
                    # Run agent synchronously in this thread
                    state = run_async(agent.run(content, session_id=session_id))
                    ws.send(json.dumps({
                        'type': 'chat_response',
                        'content': state.final_response or '',
                        'tool_calls': state.tool_calls_made,
                        'tokens_used': state.tokens_used
                    }))
                except Exception as e:
                    log.error(f"Chat error: {e}", exc_info=True)
                    ws.send(json.dumps({
                        'type': 'error',
                        'content': str(e)
                    }))

            elif msg_type == 'research':
                query = message.get('query', '')
                domain = message.get('domain', 'auto')
                if not query:
                    continue

                try:
                    prompt = f"Research: {query}"
                    if domain != 'auto':
                        prompt += f" (domain: {domain})"
                    state = run_async(agent.run(prompt, session_id="research"))
                    ws.send(json.dumps({
                        'type': 'chat_response',
                        'content': state.final_response or ''
                    }))
                except Exception as e:
                    ws.send(json.dumps({
                        'type': 'error',
                        'content': str(e)
                    }))

            elif msg_type == 'dream':
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

    except Exception as e:
        log.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        _connected_ws_clients.discard(ws)


# ===== Main =====

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zenith-OS Web Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n  Zenith-OS Server")
    print(f"  ================")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
