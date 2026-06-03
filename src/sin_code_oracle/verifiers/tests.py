"""Test execution verifier — runs pytest or a custom test command in a subprocess.

This is the most "real" verifier in the package: it actually executes the
user's tests and reports failures. Default command is `pytest`; override
with `test_command` for other test runners (e.g. `["unittest", "discover"]`).

The verifier distinguishes three outcomes:
  - PASS: all tests passed (or no tests were collected — exit 5).
  - WARN: pytest is not installed; the verifier couldn't run.
  - FAIL: tests failed OR the run timed out.

Docs: tests.doc.md
"""
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_tests(test_command: str | None = None, cwd: str | Path = ".") -> Verdict:
    """Run `test_command` in `cwd` and parse the output for failure counts.

    Args:
        test_command: Command string OR argv list. If a string, split on
                      whitespace. Defaults to `["pytest"]`.
        cwd: Working directory for the test process. Defaults to ".".

    Returns:
        Verdict. PASS if all tests passed (or no tests collected).
        WARN if pytest is missing. FAIL on any test failure or timeout.
    """
    issues: list[Issue] = []
    # Accept either a string ("pytest -x") or an argv list (["pytest", "-x"]).
    # String form is convenient for the CLI; argv form avoids shell escaping.
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

    # Parse failures from stdout. Pytest's summary line has a canonical
    # form like "5 passed, 1 failed in 0.34s" — we just scan for any line
    # containing "failed" and pick the first integer off it. Crude but
    # robust against pytest version drift.
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
                    # A non-numeric token in a "failed" line — ignore.
                    pass
    # pytest exit code 5 = no tests collected (not a failure).
    # Any other non-zero exit code means "something went wrong" and we
    # conservatively count that as at least one failure.
    if returncode != 0 and returncode != 5:
        failures = max(failures, 1)

    if failures:
        # Keep stdout/stderr tails in `details` so consumers can debug
        # without re-running pytest. 2 KB each is a reasonable default.
        issues.append(
            Issue(
                verifier="tests",
                severity="high",
                message=f"{failures} test(s) failed",
                details={"stdout": stdout[:2000], "stderr": stderr[:2000]},
            )
        )

    summary = f"Tests: {failures} failure(s), returncode={returncode}"
    # Exit 0 = all green; exit 5 = no tests collected (still considered PASS
    # here — the consumer can inspect `summary` if they want to distinguish).
    if not failures and returncode in (0, 5):
        return Verdict(status=VerdictStatus.PASS, issues=issues, summary=summary)
    return Verdict.from_issues(issues, summary)
