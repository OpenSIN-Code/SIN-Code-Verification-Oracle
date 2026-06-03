"""Security verification using Bandit plus basic safety heuristics.

Bandit is the ground truth here — it has a comprehensive Python AST walker
and a vetted rule set. We shell out to its CLI, parse the JSON output, and
map each finding to an `Issue`.

Docs: security.doc.md
"""
import json
import tempfile
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


def verify_security(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Run `bandit` against a code snippet or a path and return a Verdict.

    Args:
        code: Source code string. If provided, written to a temp file first.
        path: Path to a file or directory. Mutually exclusive with `code`.

    Returns:
        Verdict. A `WARN` Verdict with an info-level Issue is returned if
        bandit is not installed (soft failure, not a hard fail).
    """
    issues: list[Issue] = []
    target = None
    if code is not None:
        # Bandit needs a file path; tempfile is the cleanest way to give it
        # one for a code snippet.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            target = f.name
    elif path is not None:
        target = str(path)
    else:
        return Verdict(status=VerdictStatus.ERROR, issues=[], summary="No target provided")

    try:
        # -ll = medium and high severity only (skip low).
        # -ii = medium and high confidence only (skip low).
        # Together: surface only the high-signal findings.
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
            # Bandit can emit non-JSON when it crashes or is interrupted;
            # treat that as "no findings" rather than failing the verifier.
            data = {"results": []}

        # Bandit reports severity in CAPS; our Verdict convention is lowercase.
        severity_map = {"low": "low", "medium": "medium", "high": "high"}
        for item in data.get("results", []):
            severity = item.get("issue_severity", "LOW").lower()
            mapped = severity_map.get(severity, "low")
            issues.append(
                Issue(
                    verifier="security",
                    severity=mapped,
                    message=item.get("issue_text", "Security issue"),
                    file=item.get("filename"),
                    line=item.get("line_number"),
                    code=item.get("code"),
                    # `test_id` (e.g. "B105") is the Bandit rule that fired —
                    # useful for "why did this fail" debug output.
                    details={"test_id": item.get("test_id")},
                )
            )
    finally:
        # Clean up temp file ONLY when we created it (i.e. code=... was used).
        # If the caller passed `path=...`, it's their file to manage.
        if code is not None and target and os.path.exists(target):
            os.unlink(target)

    summary = f"Security scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
