"""App registry — maps @app_name to executable paths.

When user types @chrome, the agent knows exactly which app to use.
No guessing, no searching — direct mapping.

Usage in CLI:
    @chrome open google.com    → opens Chrome with URL
    @notepad open file.txt     → opens Notepad with file
    @code open project/        → opens VS Code with folder
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Dict, Optional


# Common app mappings (Windows)
_WINDOWS_APPS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
    "code": [
        r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.getenv("USERNAME", "")),
    ],
    "notepad": ["notepad.exe"],
    "explorer": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "terminal": ["wt.exe"],
    "docker": ["docker.exe"],
    "git": ["git.exe"],
    "python": ["python.exe"],
    "node": ["node.exe"],
    "npm": ["npm.cmd"],
    "pip": ["pip.exe"],
}

# macOS app mappings
_MACOS_APPS = {
    "chrome": ["/Applications/Google Chrome.app"],
    "firefox": ["/Applications/Firefox.app"],
    "safari": ["/Applications/Safari.app"],
    "code": ["/Applications/Visual Studio Code.app"],
    "terminal": ["/Applications/Utilities/Terminal.app"],
    "finder": ["/Applications/Finder.app"],
}

# Linux app mappings
_LINUX_APPS = {
    "chrome": ["google-chrome", "google-chrome-stable"],
    "firefox": ["firefox"],
    "code": ["code"],
    "terminal": ["gnome-terminal", "konsole", "xterm"],
    "nautilus": ["nautilus"],
}


class AppRegistry:
    def __init__(self):
        self._apps: Dict[str, dict] = {}
        self._load_system_apps()
        self._load_user_apps()

    def _load_system_apps(self):
        """Load system app mappings based on OS."""
        import sys
        if sys.platform == "win32":
            app_map = _WINDOWS_APPS
        elif sys.platform == "darwin":
            app_map = _MACOS_APPS
        else:
            app_map = _LINUX_APPS

        for name, paths in app_map.items():
            for p in paths:
                expanded = os.path.expandvars(p)
                if os.path.exists(expanded) or shutil.which(expanded):
                    self._apps[name] = {
                        "name": name,
                        "path": expanded,
                        "found": True,
                    }
                    break
            else:
                # Register even if not found (might be in PATH)
                self._apps[name] = {
                    "name": name,
                    "path": paths[0] if paths else "",
                    "found": bool(shutil.which(paths[0])) if paths else False,
                }

    def _load_user_apps(self):
        """Load user-defined app mappings from config."""
        user_config = Path(__file__).parent / "apps.yaml"
        if user_config.exists():
            try:
                import yaml
                data = yaml.safe_load(user_config.read_text(encoding="utf-8")) or {}
                for name, path in data.items():
                    if isinstance(path, str):
                        self._apps[name.lower()] = {
                            "name": name.lower(),
                            "path": os.path.expandvars(path),
                            "found": os.path.exists(os.path.expandvars(path)),
                        }
            except Exception:
                pass

    def resolve(self, name: str) -> Optional[dict]:
        """Resolve @app_name to an app entry."""
        name = name.lower().strip()
        return self._apps.get(name)

    def get_launch_command(self, name: str, args: str = "") -> Optional[str]:
        """Get the command to launch an app."""
        app = self.resolve(name)
        if not app:
            return None
        path = app["path"]
        if args:
            return f'"{path}" {args}' if " " in path else f"{path} {args}"
        return f'"{path}"' if " " in path else path

    def list_apps(self) -> list:
        """List all registered apps."""
        return [
            {"name": a["name"], "path": a["path"], "available": a["found"]}
            for a in self._apps.values()
        ]


# Singleton
_registry = None


def get_app_registry() -> AppRegistry:
    global _registry
    if _registry is None:
        _registry = AppRegistry()
    return _registry
