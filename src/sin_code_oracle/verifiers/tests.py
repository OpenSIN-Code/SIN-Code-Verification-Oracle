# Purpose: Test execution verifier running pytest or a custom test command in isolated subprocess.
# Docs: tests.doc.md
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_tests(test_command: str | None = None, cwd: str | Path = ".") -> Verdict:
    """Run tests in isolated subprocess.

    If test_command is None, defaults to 'pytest'.
    """
    issues: list[Issue] = []
    cmd = test_command.split() if test_command else ["pytest"]
    if not cmd:
        cmd = ["pytest"]

    result = run_command(cmd, cwd=cwd, timeout=120)

    if result["stderr"] and "Command not found" in result["stderr"]:
        issues.append(
            Issue(
                verifier="tests",
                severity="info",
                message="pytest not installed; skipping test execution",
            )
        )
        return Verdict(status=VerdictStatus.WARN, issues=issues, summary="pytest unavailable")

    if result["timed_out"]:
        issues.append(
            Issue(
                verifier="tests",
                severity="high",
                message="Test execution timed out",
            )
        )
        return Verdict.from_issues(issues, summary="Tests timed out")

    returncode = result["returncode"]
    stdout = result["stdout"]
    stderr = result["stderr"]

    # Parse failures from stdout
    failures = 0
    if "failed" in stdout:
        for line in stdout.splitlines():
            if "failed" in line.lower():
                try:
                    parts = line.split()
                    for part in parts:
                        if part.isdigit():
                            failures = int(part)
                            break
                except Exception:
                    pass
    # pytest exit code 5 = no tests collected (not a failure)
    if returncode != 0 and returncode != 5:
        failures = max(failures, 1)

    if failures:
        issues.append(
            Issue(
                verifier="tests",
                severity="high",
                message=f"{failures} test(s) failed",
                details={"stdout": stdout[:2000], "stderr": stderr[:2000]},
            )
        )

    summary = f"Tests: {failures} failure(s), returncode={returncode}"
    if not failures and returncode in (0, 5):
        return Verdict(status=VerdictStatus.PASS, issues=[], summary=summary)
    return Verdict.from_issues(issues, summary)
