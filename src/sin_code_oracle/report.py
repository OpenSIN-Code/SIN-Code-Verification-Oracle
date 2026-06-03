"""Report formatting and aggregation helpers for the Verification Oracle.

Two responsibilities:
  - `format_verdict`: turn a `Verdict` into a multi-line human-readable string
    (suitable for printing to a terminal or log file).
  - `merge_verdicts`: combine a list of `Verdict` objects into a single one
    whose status is the worst of the inputs (PASS < WARN < FAIL < ERROR).

Docs: report.doc.md
"""
from typing import Any
from .verdict import Verdict, Issue


# ── Formatting ─────────────────────────────────────────────────────────
def format_verdict(verdict: Verdict) -> str:
    """Render a `Verdict` as a multi-line human-readable string.

    Output shape:
        Status: PASS
        Summary: <verdict.summary>
        Issues: <count>
          [severity] verifier: message at file:line
          ...

    Useful for CLI/log output where consumers want to read the verdict
    without parsing JSON.
    """
    lines = [
        f"Status: {verdict.status.value}",
        f"Summary: {verdict.summary}",
        f"Issues: {len(verdict.issues)}",
    ]
    for issue in verdict.issues:
        loc = f" at {issue.file}:{issue.line}" if issue.file and issue.line else ""
        lines.append(f"  [{issue.severity}] {issue.verifier}: {issue.message}{loc}")
    return "\n".join(lines)


# ── Aggregation ────────────────────────────────────────────────────────
def merge_verdicts(verdicts: list[Verdict]) -> Verdict:
    """Merge multiple Verdicts into a single consolidated Verdict.

    Aggregation rules:
      - **Status**: the worst of all inputs (PASS < WARN < FAIL < ERROR).
      - **Issues**: union of all input issues (duplicates preserved for trace).
      - **Diagnostics**: shallow `dict.update` — later verdicts override earlier
        keys with the same name. Per-verifier namespacing is the caller's job.
      - **Summary**: ` | `-joined concatenation of non-empty input summaries,
        or a default `"Merged N verdicts"` if all are empty.

    Args:
        verdicts: List of `Verdict` objects to merge. Empty list returns
                  a PASS Verdict with the default summary.

    Returns:
        A new `Verdict` reflecting the combined state.
    """
    from .verdict import VerdictStatus
    all_issues: list[Issue] = []
    diagnostics: dict[str, Any] = {}
    # The status order is the merge priority: a higher index means "worse".
    # index() is O(n) but n=4 — readability beats micro-optimization here.
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
