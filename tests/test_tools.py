"""Test script for tools/builtin modules."""
import asyncio
import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


async def run_all_tests():
    results = []

    # ---- imports & setup ----
    from tools.builtin import get_time, read_file, write_file, edit_file, list_dir, glob_search, grep_search, run_command, recall, store_memory
    from tools.builtin.file_ops import set_default_directory
    from tools.builtin.shell import set_default_directory as set_shell_dir
    from tools.builtin.memory_tools import set_soft_memory
    from memory.soft_memory import SoftMemory

    set_default_directory(PROJECT_ROOT)
    set_shell_dir(PROJECT_ROOT)
    sm = SoftMemory()
    set_soft_memory(sm)

    # helper
    def check(name, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        tag = f"  [{status}] {name}"
        if detail:
            tag += f"  -- {detail}"
        print(tag)
        results.append((name, condition))

    # ---- Test 1: get_time ----
    r = await get_time({})
    check(
        "get_time",
        r.get("success") is True
        and isinstance(r.get("data"), dict)
        and all(k in r["data"] for k in ("datetime", "date", "time", "day")),
        detail=f"data keys={list(r.get('data', {}).keys())}",
    )

    # ---- Test 2: read_file (existing) ----
    r = await read_file({"path": "config/codebook.yaml"})
    check(
        "read_file (existing)",
        r.get("success") is True and "content" in r.get("data", {}),
        detail=f"success={r.get('success')}",
    )

    # ---- Test 3: read_file (nonexistent) ----
    r = await read_file({"path": "nonexistent.txt"})
    check(
        "read_file (nonexistent)",
        r.get("success") is False and "error" in r,
        detail=f"error={r.get('error', '')[:60]}",
    )

    # ---- Test 4: write_file ----
    r = await write_file({"path": "test_output.txt", "content": "hello"})
    check(
        "write_file",
        r.get("success") is True,
        detail=f"success={r.get('success')}",
    )

    # ---- Test 5: list_dir ----
    r = await list_dir({"path": "."})
    check(
        "list_dir",
        r.get("success") is True
        and isinstance(r.get("data", {}).get("entries"), list),
        detail=f"entries count={r.get('data', {}).get('count')}",
    )

    # ---- Test 6: run_command ----
    r = await run_command({"command": "echo hello"})
    check(
        "run_command",
        r.get("success") is True and "hello" in r.get("data", {}).get("stdout", ""),
        detail=f"stdout={r.get('data', {}).get('stdout', '')[:60]}",
    )

    # ---- Test 7: recall ----
    r = await recall({"query": "test"})
    check(
        "recall",
        isinstance(r, dict) and "success" in r,
        detail=f"success={r.get('success')}",
    )

    # ---- Test 8: store_memory ----
    r = await store_memory({"content": "test memory"})
    check(
        "store_memory",
        r.get("success") is True,
        detail=f"data={r.get('data', '')[:60]}",
    )

    # ---- Test 9: read_file with start_line/end_line ----
    r = await read_file({"path": "config/codebook.yaml", "start_line": 1, "end_line": 5})
    check(
        "read_file (start_line/end_line)",
        r.get("success") is True
        and r.get("data", {}).get("start_line") == 1
        and r.get("data", {}).get("end_line") == 5
        and "numbered" in r.get("data", {}),
        detail=f"lines={r.get('data', {}).get('start_line')}-{r.get('data', {}).get('end_line')}",
    )

    # ---- Test 10: edit_file with diff output ----
    # Create a test file first
    await write_file({"path": "test_edit.txt", "content": "line1\nline2\nline3\n"})
    r = await edit_file({"path": "test_edit.txt", "old_text": "line2", "new_text": "LINE2"})
    check(
        "edit_file (diff output)",
        r.get("success") is True
        and "diff" in r.get("data", {})
        and r.get("data", {}).get("lines_changed", 0) > 0,
        detail=f"lines_changed={r.get('data', {}).get('lines_changed')}",
    )

    # ---- Test 11: edit_file with flexible matching ----
    await write_file({"path": "test_flex.txt", "content": "hello   world\nfoo\n"})
    r = await edit_file({"path": "test_flex.txt", "old_text": "hello world", "new_text": "hi world", "flexible": True})
    check(
        "edit_file (flexible matching)",
        r.get("success") is True,
        detail=f"replacements={r.get('data', {}).get('replacements')}",
    )

    # ---- Test 12: glob_search ----
    r = await glob_search({"pattern": "*.yaml", "path": "config"})
    check(
        "glob_search",
        r.get("success") is True
        and isinstance(r.get("data", {}).get("matches"), list)
        and r.get("data", {}).get("count", 0) > 0,
        detail=f"matches={r.get('data', {}).get('count')}",
    )

    # ---- Test 13: grep_search ----
    r = await grep_search({"pattern": "def test_", "path": "tests", "glob": "*.py", "output_mode": "count"})
    check(
        "grep_search",
        r.get("success") is True
        and r.get("data", {}).get("count", 0) > 0,
        detail=f"count={r.get('data', {}).get('count')}",
    )

    # ---- cleanup ----
    try:
        for f in ["test_output.txt", "test_edit.txt", "test_flex.txt"]:
            cleanup_path = os.path.join(PROJECT_ROOT, f)
            if os.path.exists(cleanup_path):
                os.remove(cleanup_path)
        print("\n  Cleaned up test files")
    except Exception as e:
        print(f"\n  Cleanup warning: {e}")

    # ---- summary ----
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"  Results: {passed}/{total} passed")
    if passed == total:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED")
    print(f"{'='*40}")
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
