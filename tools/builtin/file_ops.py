import os
from pathlib import Path


async def read_file(params: dict) -> dict:
    """Read file contents.
    params: {path: str}
    """
    path = params.get("path")
    if not path:
        return {"success": False, "error": "Missing 'path' parameter"}

    try:
        content = Path(path).read_text(encoding="utf-8")
        return {"success": True, "data": {"content": content, "path": path}}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def write_file(params: dict) -> dict:
    """Write content to file.
    params: {path: str, content: str}
    """
    path = params.get("path")
    content = params.get("content")
    if not path:
        return {"success": False, "error": "Missing 'path' parameter"}
    if content is None:
        return {"success": False, "error": "Missing 'content' parameter"}

    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")
        return {"success": True, "data": {"path": path, "bytes_written": len(content.encode("utf-8"))}}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_dir(params: dict) -> dict:
    """List directory contents.
    params: {path: str}
    """
    path = params.get("path", ".")

    try:
        entries = []
        for entry in os.scandir(path):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"success": True, "data": {"path": path, "entries": entries, "count": len(entries)}}
    except FileNotFoundError:
        return {"success": False, "error": f"Directory not found: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
