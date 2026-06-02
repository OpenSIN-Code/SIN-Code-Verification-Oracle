# Purpose: Report formatting and aggregation helpers for VerificationOracle.
# Docs: report.doc.md
from typing import Any
from .verdict import Verdict, Issue


def format_verdict(verdict: Verdict) -> str:
    """Human-readable summary of a Verdict."""
    lines = [
        f"Status: {verdict.status.value}",
        f"Summary: {verdict.summary}",
        f"Issues: {len(verdict.issues)}",
    ]
    for issue in verdict.issues:
        loc = f" at {issue.file}:{issue.line}" if issue.file and issue.line else ""
        lines.append(f"  [{issue.severity}] {issue.verifier}: {issue.message}{loc}")
    return "\n".join(lines)


def merge_verdicts(verdicts: list[Verdict]) -> Verdict:
    """Merge multiple Verdicts into a single Verdict.

    Overall status is the worst of the set.
    """
    from .verdict import VerdictStatus
    all_issues: list[Issue] = []
    diagnostics: dict[str, Any] = {}
    status_order = [VerdictStatus.PASS, VerdictStatus.WARN, VerdictStatus.FAIL, VerdictStatus.ERROR]
    worst = VerdictStatus.PASS
    summaries: list[str] = []
    for v in verdicts:
        all_issues.extend(v.issues)
        summaries.append(v.summary)
        diagnostics.update(v.diagnostics)
        if status_order.index(v.status) > status_order.index(worst):
            worst = v.status
    summary = " | ".join(filter(None, summaries)) or f"Merged {len(verdicts)} verdicts"
    return Verdict(
        status=worst,
        issues=all_issues,
        summary=summary,
        diagnostics=diagnostics,
    )
