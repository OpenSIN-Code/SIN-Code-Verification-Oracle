# Purpose: Verdict data models and status enums for the Verification Oracle.
# Docs: verdict.doc.md
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
from pathlib import Path
from typing import Any


class VerdictStatus(Enum):
    """Overall status of a verification run."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class Issue:
    """A single issue found during verification."""
    verifier: str
    severity: str  # critical, high, medium, low, info
    message: str
    file: str | None = None
    line: int | None = None
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier": self.verifier,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "code": self.code,
            "details": self.details,
        }


@dataclass
class Verdict:
    """Aggregated result from one or more verifiers."""
    status: VerdictStatus
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary,
            "diagnostics": self.diagnostics,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_issues(cls, issues: list[Issue], summary: str = "") -> "Verdict":
        status = VerdictStatus.PASS
        for issue in issues:
            if issue.severity in ("critical", "high"):
                status = VerdictStatus.FAIL
                break
            elif issue.severity in ("medium", "low"):
                status = VerdictStatus.WARN
        return cls(status=status, issues=issues, summary=summary)
