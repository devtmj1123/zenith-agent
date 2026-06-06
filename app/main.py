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


def wait_for_server(port: int, timeout: int = 10):
    """Wait for the server to be ready."""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f'http://127.0.0.1:{port}/', timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def main():
    """Launch Zenith-OS desktop application."""
    try:
        import webview
    except ImportError:
        print("pywebview not installed. Run: pip install pywebview")
        print("Falling back to browser mode...")
        return main_browser()

    # Find a free port
    port = find_free_port()
    print(f"\n  Zenith-OS Desktop")
    print(f"  ================")
    print(f"  Starting server on port {port}...")

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        print("  ERROR: Server failed to start")
        return 1

    print(f"  Server ready at http://127.0.0.1:{port}")
    print(f"  Opening native window...\n")

    # Create native window
    window = webview.create_window(
        title='Zenith-OS',
        url=f'http://127.0.0.1:{port}',
        width=1280,
        height=800,
        min_size=(800, 600),
        resizable=True,
        text_select=True,
    )

    # Start the webview event loop
    webview.start(debug=False)

    return 0


def main_browser():
    """Fallback: open in default browser."""
    import webbrowser

    port = find_free_port()
    print(f"\n  Zenith-OS Web")
    print(f"  =============")
    print(f"  Starting server on port {port}...")

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        print("  ERROR: Server failed to start")
        return 1

    url = f'http://127.0.0.1:{port}'
    print(f"  Server ready at {url}")
    print(f"  Opening browser...\n")

    webbrowser.open(url)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
