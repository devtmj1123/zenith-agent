"""Tests for core/physical_intuition.py — PhysicalIntuition.validate_action and get_context_constraints."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.physical_intuition import PhysicalIntuition, ValidationLevel


def run_tests():
    pi = PhysicalIntuition()
    results = []

    # 1. read_file with valid path => ALLOW
    v = pi.validate_action("read_file", {"path": "test.txt"})
    results.append(("1. read_file('test.txt') => ALLOW", v.level == ValidationLevel.ALLOW))

    # 2. delete_file on protected root "/" => DENY
    v = pi.validate_action("delete_file", {"path": "/"})
    results.append(("2. delete_file('/') => DENY (protected root)", v.level == ValidationLevel.DENY))

    # 3. delete_file on C:\Windows => DENY
    v = pi.validate_action("delete_file", {"path": "C:\\Windows"})
    results.append(("3. delete_file('C:\\Windows') => DENY", v.level == ValidationLevel.DENY))

    # 4. run_command with 'rm -rf /' => DENY
    v = pi.validate_action("run_command", {"command": "rm -rf /"})
    results.append(("4. run_command('rm -rf /') => DENY", v.level == ValidationLevel.DENY))

    # 5. run_command with 'ls' => ALLOW
    v = pi.validate_action("run_command", {"command": "ls"})
    results.append(("5. run_command('ls') => ALLOW", v.level == ValidationLevel.ALLOW))

    # 6. run_command with 'sudo apt install' => WARN
    v = pi.validate_action("run_command", {"command": "sudo apt install"})
    results.append(("6. run_command('sudo apt install') => WARN", v.level == ValidationLevel.WARN))

    # 7. navigate to valid URL => ALLOW
    v = pi.validate_action("navigate", {"url": "http://example.com"})
    results.append(("7. navigate('http://example.com') => ALLOW", v.level == ValidationLevel.ALLOW))

    # 8. navigate to malformed URL => WARN
    v = pi.validate_action("navigate", {"url": "not-a-url"})
    results.append(("8. navigate('not-a-url') => WARN", v.level == ValidationLevel.WARN))

    # 9. read_file with empty path => DENY
    v = pi.validate_action("read_file", {"path": ""})
    results.append(("9. read_file('') => DENY", v.level == ValidationLevel.DENY))

    # 10. get_context_constraints("read a file") contains "Files"
    c = pi.get_context_constraints("read a file")
    results.append(("10. get_context_constraints('read a file') contains 'Files'", "Files" in c))

    # 11. get_context_constraints("hello") returns empty string
    c = pi.get_context_constraints("hello")
    results.append(("11. get_context_constraints('hello') => empty string", c == ""))

    # Print results
    all_pass = True
    for label, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {status}  {label}")

    print()
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"Results: {passed_count}/{total} passed")
    return all_pass


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
