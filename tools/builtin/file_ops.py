import difflib
import fnmatch
import os
import re
import subprocess
from pathlib import Path


# Default working directory — set to Zenith project root
_DEFAULT_DIR = str(Path(__file__).resolve().parent.parent.parent)


def set_default_directory(path: str):
    """Set the default working directory for file operations."""
    global _DEFAULT_DIR
    _DEFAULT_DIR = str(Path(path).resolve())


def _resolve_path(path: str) -> Path:
    """Resolve path relative to default directory if not absolute."""
    p = Path(path)
    if p.is_absolute():
        return p
    return Path(_DEFAULT_DIR) / p


async def read_file(params: dict) -> dict:
    """Read file contents with optional offset/limit or start_line/end_line.

    params: {path: str, offset?: int, limit?: int, start_line?: int, end_line?: int}
    offset: 0-based line number to start from (default: 0)
    limit: max lines to read (default: 500)
    start_line/end_line: 1-based inclusive line range (overrides offset/limit)
    """
    path = params.get("path")
    if not path:
        return {"success": False, "error": "Missing 'path' parameter"}

    try:
        resolved = _resolve_path(path)
        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path}"}

        content = resolved.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # start_line/end_line takes precedence (1-based inclusive)
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        if start_line is not None or end_line is not None:
            offset = (start_line or 1) - 1  # Convert to 0-based
            end = end_line or total_lines  # Inclusive
            limit = end - offset
        else:
            offset = params.get("offset", 0)
            limit = params.get("limit", 500)

        # Slice
        selected = lines[offset:offset + limit]
        truncated = (offset + limit) < total_lines
        content_text = "".join(selected)

        # Add line numbers for easy reference
        numbered_lines = []
        for i, line in enumerate(selected):
            numbered_lines.append(f"{offset + i + 1:4d} | {line.rstrip()}")
        numbered_content = "\n".join(numbered_lines)

        result = {
            "content": content_text,
            "numbered": numbered_content,
            "path": str(resolved),
            "total_lines": total_lines,
            "offset": offset,
            "limit": limit,
            "start_line": offset + 1,
            "end_line": min(offset + len(selected), total_lines),
        }
        if truncated:
            result["truncated"] = True
            result["next_offset"] = offset + limit

        return {"success": True, "data": result}
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
        resolved = _resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"success": True, "data": {"path": str(resolved), "bytes_written": len(content.encode("utf-8"))}}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_dir(params: dict) -> dict:
    """List directory contents.
    params: {path: str}
    """
    path = params.get("path", ".")

    try:
        resolved = _resolve_path(path)
        entries = []
        for entry in os.scandir(resolved):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"success": True, "data": {"path": str(resolved), "entries": entries, "count": len(entries)}}
    except FileNotFoundError:
        return {"success": False, "error": f"Directory not found: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def edit_file(params: dict) -> dict:
    """Edit file: find and replace text with flexible matching.

    params: {path, old_text, new_text, replace_all?, flexible?}
    replace_all: if false (default), fails when old_text matches multiple times.
    flexible: if true, normalizes whitespace before matching (handles tabs vs spaces, trailing whitespace).
    Returns a unified diff showing what changed.
    """
    path = params.get("path")
    old_text = params.get("old_text")
    new_text = params.get("new_text")
    replace_all = params.get("replace_all", False)
    flexible = params.get("flexible", False)

    if not path:
        return {"success": False, "error": "Missing 'path' parameter"}
    if old_text is None:
        return {"success": False, "error": "Missing 'old_text' parameter"}
    if new_text is None:
        return {"success": False, "error": "Missing 'new_text' parameter"}

    try:
        resolved = _resolve_path(path)
        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path}"}

        content = resolved.read_text(encoding="utf-8")

        if flexible:
            # Normalize whitespace: collapse runs of whitespace, strip trailing
            def _norm_ws(s: str) -> str:
                return re.sub(r'[ \t]+', ' ', s.strip())

            norm_old = _norm_ws(old_text)
            norm_content = _norm_ws(content)

            # Find matches in normalized space, apply in original
            count = norm_content.count(norm_old)
            if count == 0:
                return {"success": False, "error": f"Text not found (flexible): {old_text[:80]}"}

            if count > 1 and not replace_all:
                return {
                    "success": False,
                    "error": f"old_text found {count} times (flexible). Provide more context or set replace_all=true.",
                    "occurrences": count,
                }

            # Use original text for replacement (preserve surrounding formatting)
            count = content.count(old_text)
            if count > 0:
                # Exact match exists — use it
                new_content = content.replace(old_text, new_text, 1 if not replace_all else -1)
                actual_count = count if replace_all else 1
            else:
                # Need line-by-line flexible match
                old_lines = old_text.splitlines()
                content_lines = content.splitlines()
                match_indices = []
                for i in range(len(content_lines) - len(old_lines) + 1):
                    window = content_lines[i:i + len(old_lines)]
                    if all(_norm_ws(a) == _norm_ws(b) for a, b in zip(old_lines, window)):
                        match_indices.append(i)

                if not match_indices:
                    return {"success": False, "error": f"Text not found (flexible line match): {old_text[:80]}"}
                if len(match_indices) > 1 and not replace_all:
                    return {
                        "success": False,
                        "error": f"old_text found {len(match_indices)} times (flexible). Set replace_all=true.",
                        "occurrences": len(match_indices),
                    }

                # Replace matched lines
                new_lines = content_lines[:]
                for idx in (match_indices if replace_all else match_indices[:1]):
                    new_lines[idx:idx + len(old_lines)] = new_text.splitlines()
                new_content = "\n".join(new_lines)
                actual_count = len(match_indices) if replace_all else 1
        else:
            # Exact matching
            count = content.count(old_text)
            if count == 0:
                return {"success": False, "error": f"Text not found in file: {old_text[:80]}"}
            if count > 1 and not replace_all:
                return {
                    "success": False,
                    "error": f"old_text found {count} times. Provide more context or set replace_all=true.",
                    "occurrences": count,
                }
            new_content = content.replace(old_text, new_text, 1 if not replace_all else -1)
            actual_count = count if replace_all else 1

        # Generate unified diff
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{resolved.name}",
            tofile=f"b/{resolved.name}",
            n=3
        ))
        diff_text = "".join(diff)

        resolved.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "data": {
                "path": str(resolved),
                "replacements": actual_count,
                "diff": diff_text,
                "lines_changed": sum(1 for line in diff if line.startswith('+') and not line.startswith('+++')),
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def delete_file(params: dict) -> dict:
    """Delete a file.
    params: {path: str}
    """
    path = params.get("path")
    if not path:
        return {"success": False, "error": "Missing 'path' parameter"}

    try:
        resolved = _resolve_path(path)
        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path}"}

        resolved.unlink()
        return {"success": True, "data": {"path": str(resolved), "deleted": True}}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def glob_search(params: dict) -> dict:
    """Find files matching a glob pattern.

    params: {pattern: str, path?: str}
    pattern: glob pattern like "**/*.py", "src/**/*.ts", "*.md"
    path: directory to search in (default: project root)
    Returns up to 100 matching file paths.
    """
    pattern = params.get("pattern")
    if not pattern:
        return {"success": False, "error": "Missing 'pattern' parameter"}

    search_dir = params.get("path", ".")
    try:
        resolved = _resolve_path(search_dir)
        if not resolved.exists():
            return {"success": False, "error": f"Directory not found: {search_dir}"}

        matches = list(resolved.glob(pattern))
        # Filter to files only (not dirs), cap at 100
        files = [str(m.relative_to(resolved)) for m in matches if m.is_file()][:100]
        return {
            "success": True,
            "data": {
                "pattern": pattern,
                "path": str(resolved),
                "matches": files,
                "count": len(files),
                "truncated": len(matches) > 100,
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def grep_search(params: dict) -> dict:
    """Search file contents using regex.

    params: {pattern: str, path?: str, glob?: str, output_mode?: str}
    pattern: regex pattern to search for
    path: file or directory to search (default: project root)
    glob: file filter like "*.py" or "*.ts"
    output_mode: "files_with_matches" (default), "content", "count"
    Returns matching files, content with context, or counts.
    """
    pattern = params.get("pattern")
    if not pattern:
        return {"success": False, "error": "Missing 'pattern' parameter"}

    search_path = params.get("path", ".")
    file_glob = params.get("glob", "")
    output_mode = params.get("output_mode", "files_with_matches")

    try:
        resolved = _resolve_path(search_path)

        # Try ripgrep first (fast), fall back to Python
        try:
            result = _grep_with_rg(pattern, str(resolved), file_glob, output_mode)
            if result is not None:
                return {"success": True, "data": result}
        except FileNotFoundError:
            pass  # rg not installed, use Python fallback

        result = _grep_with_python(pattern, resolved, file_glob, output_mode)
        return {"success": True, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _grep_with_rg(pattern: str, path: str, glob: str, output_mode: str) -> dict | None:
    """Use ripgrep for fast searching."""
    cmd = ["rg", "--no-heading", "-n"]
    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    # content mode: default rg output with line numbers

    if glob:
        cmd.extend(["-g", glob])

    cmd.extend(["-e", pattern, path])

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if proc.returncode > 1:
        return None  # rg error, fall back to Python

    lines = proc.stdout.strip().split("\n") if proc.stdout.strip() else []

    if output_mode == "count":
        # Parse count output: "file:count"
        total = 0
        for line in lines:
            if ":" in line:
                try:
                    total += int(line.rsplit(":", 1)[1])
                except ValueError:
                    pass
        return {"count": total, "files": lines}
    elif output_mode == "content":
        # Limit to 200 lines to avoid flooding
        if len(lines) > 200:
            lines = lines[:200]
            truncated = True
        else:
            truncated = False
        return {"content": "\n".join(lines), "line_count": len(lines), "truncated": truncated}
    else:
        return {"files": lines, "count": len(lines)}


def _grep_with_python(pattern: str, path: Path, glob: str, output_mode: str) -> dict:
    """Python fallback for grep when ripgrep isn't installed."""
    regex = re.compile(pattern)
    matches = []

    if path.is_file():
        files = [path]
    else:
        if glob:
            files = list(path.rglob(glob))[:500]
        else:
            files = [f for f in path.rglob("*") if f.is_file()][:500]

    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if output_mode == "files_with_matches":
            if regex.search(text):
                matches.append(str(fpath))
        elif output_mode == "content":
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{fpath}:{i}: {line}")
                    if len(matches) >= 200:
                        break
        elif output_mode == "count":
            count = len(regex.findall(text))
            if count > 0:
                matches.append(f"{fpath}:{count}")

        if len(matches) >= 200:
            break

    if output_mode == "count":
        total = 0
        for m in matches:
            try:
                total += int(m.rsplit(":", 1)[1])
            except ValueError:
                pass
        return {"count": total, "files": matches}
    elif output_mode == "content":
        return {"content": "\n".join(matches), "line_count": len(matches), "truncated": len(matches) >= 200}
    else:
        return {"files": matches, "count": len(matches)}
