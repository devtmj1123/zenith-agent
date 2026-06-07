"""Zenith-OS Desktop Application.

Launches the Flask server and opens a native window using pywebview.
"""
from __future__ import annotations
import os
import sys
import threading
import time
from pathlib import Path

# Add parent directory to path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def find_free_port():
    """Find a free port on localhost."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_server(port: int):
    """Run the Flask server in a background thread."""
    from app.server import app
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


def wait_for_server(port: int, timeout: int = 15):
    """Wait for the server to be ready."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1)
            if req.getcode() == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main():
    """Launch Zenith-OS desktop application."""
    port = find_free_port()
    print()
    print("  Zenith-OS")
    print("  =========")

    # Preload embedding model before starting server
    print("  Loading embedding model...")
    try:
        from memory.soft_memory import SoftMemory
        _mem = SoftMemory()  # This loads the model
        print("  Model loaded.")
    except Exception as e:
        print(f"  Warning: Model load failed: {e}")

    # Preload agent (connects to LLM, loads tools)
    print("  Initializing agent...")
    try:
        from app.server import get_agent
        get_agent()
        print("  Agent ready.")
    except Exception as e:
        print(f"  Warning: Agent init failed: {e}")

    print(f"  Starting server on port {port}...")

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        print("  ERROR: Server failed to start. Check for errors above.")
        input("  Press Enter to exit...")
        return 1

    url = f'http://127.0.0.1:{port}'
    print(f"  Server ready at {url}")

    # Try native window first
    try:
        import webview
        print("  Opening native window...")
        window = webview.create_window(
            title='Zenith-OS',
            url=url,
            width=1280,
            height=800,
            min_size=(800, 600),
            resizable=True,
            text_select=True,
        )
        webview.start(debug=False)
        return 0
    except ImportError:
        print("  pywebview not installed, opening browser...")
    except Exception as e:
        print(f"  pywebview error: {e}, opening browser...")

    # Fallback to browser
    import webbrowser
    webbrowser.open(url)
    print("  Opened in browser. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
