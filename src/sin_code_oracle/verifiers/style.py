"""Style verification using Ruff (lint + format check).

Two Ruff subcommands are run:
  - `ruff check`         → JSON list of lint findings.
  - `ruff format --check` → exit 1 if the file isn't formatted; we surface
                              that as a low-severity Issue.

Severity mapping: any ruff code starting with `E` (pycodestyle errors) is
`medium`; everything else (warnings, conventions) is `low`. This matches
the common intuition that `E` codes are real bugs while `W` codes are
stylistic.

Docs: style.doc.md
"""
import tempfile
import os
import json
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_style(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Run `ruff check` and `ruff format --check` on a code snippet or path.

    Args:
        code: Source code string. Written to a tempfile first.
        path: Path to a file or directory. Mutually exclusive with `code`.

    Returns:
        Verdict. `WARN` if ruff is missing; `PASS`/`FAIL` otherwise.
    """
    issues: list[Issue] = []
    target = None
    if code is not None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            target = f.name
    elif path is not None:
        target = str(path)
    else:
        return Verdict(status=VerdictStatus.ERROR, issues=[], summary="No target provided")

    try:
        # ── Lint pass ──
        lint_cmd = ["ruff", "check", "--output-format", "json", target]
        lint_result = run_command(lint_cmd, timeout=60)
        if lint_result["stderr"] and "Command not found" in lint_result["stderr"]:
            issues.append(
                Issue(
                    verifier="style",
                    severity="info",
                    message="ruff not installed; skipping style check",
                )
            )
            return Verdict(status=VerdictStatus.WARN, issues=issues, summary="ruff unavailable")

        try:
            lint_data = json.loads(lint_result["stdout"])
        except json.JSONDecodeError:
            # Ruff can emit non-JSON on config errors; treat as "no findings".
            lint_data = []

        for item in lint_data:
            severity = "low"
            code_val = item.get("code") or ""
            # pycodestyle error codes (E1xx, E5xx, E7xx, E9xx) → medium.
            # Everything else (W = warnings, etc.) stays low.
            if code_val.startswith("E"):
                severity = "medium"
            issues.append(
                Issue(
                    verifier="style",
                    severity=severity,
                    message=f"{item.get('code', 'RUFF')}: {item.get('message', '')}",
                    file=item.get("filename"),
                    line=item.get("location", {}).get("row") if isinstance(item.get("location"), dict) else None,
                    code=item.get("code"),
                )
            )

        # ── Format pass ──
        # --check: exit 1 if changes are needed (and print a diff).
        # We treat any non-zero return code from format --check as
        # "the file isn't formatted" — no need to parse the diff text.
        fmt_cmd = ["ruff", "format", "--check", "--diff", target]
        fmt_result = run_command(fmt_cmd, timeout=60)
        if fmt_result["stdout"] or fmt_result["stderr"]:
            # ruff format --check returns 1 if changes needed
            if fmt_result["returncode"] != 0:
                issues.append(
                    Issue(
                        verifier="style",
                        severity="low",
                        message="Code formatting does not match ruff style (run ruff format)",
                        file=target,
                    )
                )
    finally:
        # Only delete the temp file we created; never touch a caller-supplied path.
        if code is not None and target and os.path.exists(target):
            os.unlink(target)

    summary = f"Style scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
