# `verdict.py` — Verdict Data Models

What this file does: the shared data model for every verifier in the package. `VerdictStatus` is the status enum, `Issue` is a single finding, and `Verdict` is the aggregate result. `Verdict.from_issues()` auto-derives the status from issue severities.

## Dependency map

- Imports: stdlib only (`dataclasses`, `enum`, `json`).
- Imported by: every verifier module under `verifiers/`, `report.py`, `oracle.py`, `__init__.py` (re-exported), and any external user code.

## Public API

| Symbol                | Purpose                                                                |
|-----------------------|------------------------------------------------------------------------|
| `VerdictStatus`       | Enum: PASS / WARN / FAIL / ERROR. Order: PASS < WARN < FAIL < ERROR.   |
| `Issue`               | A single finding (verifier, severity, message, file, line, code, details) |
| `Issue.to_dict()`     | JSON-serializable view                                                 |
| `Verdict`             | Aggregated result (status, issues, summary, diagnostics)               |
| `Verdict.to_dict()`   | JSON-serializable view                                                 |
| `Verdict.to_json()`   | Pretty-printed JSON                                                    |
| `Verdict.from_issues(issues, summary="")` | Build a Verdict from issues; auto-derives status:   |

## Status severity rules (from_issues)

- Any issue with severity `critical` or `high` → `FAIL`
- Else any issue with severity `medium` or `low` → `WARN`
- Else → `PASS`

## Important config / limits

- **`Issue.severity` is free-form string.** The convention is `critical | high | medium | low | info`, but `from_issues` only looks at the first four. Anything else is ignored in auto-derivation.
- **`Verdict.diagnostics` is a free-form dict** for tool-specific extra data (e.g. pytest summary, bandit JSON). Consumers should not assume any particular shape.
- **`to_json()` uses `indent=2` always** — if you need compact JSON, use `to_dict()` and `json.dumps(...)` yourself.

## Design decisions

- **Why `dataclass` and not Pydantic?** `dataclass` has zero dependencies and is good enough for in-process data. Pydantic would shine if we needed validation at API boundaries, but these objects never cross one.
- **Why a free-form `severity` string?** Different verifiers use different scales (bandit: HIGH/MEDIUM/LOW, ruff: codes like E501). Normalizing to a single enum would lose information; the string lets each verifier speak its own dialect.
- **Why auto-derive status in `from_issues`?** Most callers build a Verdict from a list of issues they already collected. The auto-derivation matches the common case and avoids a 5-line boilerplate at every call site.

## Usage examples

```python
from sin_code_oracle.verdict import Verdict, VerdictStatus, Issue

# Build from issues (status auto-derived)
v = Verdict.from_issues([
    Issue(verifier="security", severity="high", message="hardcoded password", file="x.py", line=3),
    Issue(verifier="style", severity="low", message="line too long"),
])
print(v.status)  # VerdictStatus.FAIL (because of the high-severity issue)

# Build directly
v = Verdict(
    status=VerdictStatus.WARN,
    issues=[],
    summary="No issues, but tests skipped",
    diagnostics={"pytest": "no tests collected"},
)
print(v.to_json())
```

## Caveats / footguns

- **`from_issues` only checks the first `high`/`medium`/etc. and bails.** It does NOT aggregate multiple severities — a single high-severity issue sets FAIL even if 100 info issues would also be there. That's the desired behavior (worst-case), but worth knowing.
- **`Issue.details` defaults to an empty dict, not None.** This avoids `KeyError` in consumers that always do `issue.details.get(...)`.
- **Status enum values are strings (`"PASS"`, `"WARN"`, etc.)**, not integers. JSON-serializable by default.
