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
_settings = None


def get_agent():
    """Get or create the Zenith agent."""
    global _agent, _settings
    if _agent is None:
        from config.settings import Settings
        from main import build_agent

        _settings = Settings()
        _settings.load_from_env()

        _agent = build_agent(_settings, on_event=lambda e: None)
    return _agent


def run_async(coro):
    """Run async function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===== Routes =====

@app.route('/')
def index():
    return render_template('index.html')


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


# ===== WebSocket =====

@sock.route('/ws')
def websocket(ws):
    """WebSocket for real-time chat.

    IMPORTANT: flask-sock is synchronous. All work must happen in this thread.
    """
    agent = get_agent()
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
