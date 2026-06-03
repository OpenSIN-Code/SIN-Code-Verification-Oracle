# Purpose: Style verification using Ruff (format, lint, import sorting).
# Docs: style.doc.md
import tempfile
import os
import json
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_style(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Run Ruff linter and format checker on code or path."""
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
        # lint with JSON output
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
            lint_data = []

        for item in lint_data:
            severity = "low"
            code_val = item.get("code") or ""
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

        # format check
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
        if code is not None and target and os.path.exists(target):
            os.unlink(target)

    summary = f"Style scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
