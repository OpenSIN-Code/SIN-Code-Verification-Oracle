# Purpose: Security verification using Bandit and basic safety checks.
# Docs: security.doc.md
import json
import tempfile
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_security(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Run Bandit security linter on code or path."""
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
        cmd = [
            "bandit",
            "-f", "json",
            "-ll",  # medium and high severity
            "-ii",  # medium and high confidence
            target,
        ]
        result = run_command(cmd, timeout=60)
        if result["stderr"] and "Command not found" in result["stderr"]:
            issues.append(
                Issue(
                    verifier="security",
                    severity="info",
                    message="bandit not installed; skipping security scan",
                )
            )
            return Verdict(status=VerdictStatus.WARN, issues=issues, summary="bandit unavailable")

        try:
            data = json.loads(result["stdout"])
        except json.JSONDecodeError:
            data = {"results": []}

        for item in data.get("results", []):
            severity = item.get("issue_severity", "LOW").lower()
            severity_map = {"low": "low", "medium": "medium", "high": "high"}
            mapped = severity_map.get(severity, "low")
            issues.append(
                Issue(
                    verifier="security",
                    severity=mapped,
                    message=item.get("issue_text", "Security issue"),
                    file=item.get("filename"),
                    line=item.get("line_number"),
                    code=item.get("code"),
                    details={"test_id": item.get("test_id")},
                )
            )
    finally:
        if code is not None and target and os.path.exists(target):
            os.unlink(target)

    summary = f"Security scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
