# `report.py` — Verdict Formatting and Aggregation

What this file does: small helpers for human-readable formatting (`format_verdict`) and worst-case merging (`merge_verdicts`) of `Verdict` objects.

## Dependency map

- Imports: `verdict.py` (for `Verdict` and `Issue` types — `VerdictStatus` is imported lazily inside the function to break an import cycle)
- Imported by: `oracle.py` (calls `merge_verdicts` after fanning out to verifiers)

## Public API

| Function                       | Purpose                                                       |
|--------------------------------|---------------------------------------------------------------|
| `format_verdict(verdict)`      | Render a `Verdict` as a multi-line human-readable string       |
| `merge_verdicts(verdicts)`     | Combine a list of `Verdict` objects into a single `Verdict`   |

## Important config / limits

- **`merge_verdicts` status order is fixed:** PASS < WARN < FAIL < ERROR. The merged status is the worst of the inputs.
- **Issue list is concatenated, not deduplicated.** If the same finding comes from two verifiers, you'll see it twice — that's intentional so the consumer can attribute it.
- **Diagnostics are merged with `dict.update`** (last-writer-wins). Callers that want per-verifier namespacing must namespace their keys before calling.
- **Empty input** to `merge_verdicts([])` returns a PASS verdict with summary `"Merged 0 verdicts"`.

## Design decisions

- **Why worst-case status?** A single FAIL should not be hidden by 4 PASSes from other verifiers. The merged verdict is the most pessimistic honest answer.
- **Why lazy-import `VerdictStatus`?** It avoids a circular import: `verdict.py` doesn't import from `report.py`, but `report.py` references the status enum.
- **Why no dedup on issues?** Different verifiers may surface the same line for different reasons (e.g. bandit and ruff both flagging a `subprocess.Popen` with `shell=True`). Preserving both gives the consumer the full picture.

## Usage examples

```python
from sin_code_oracle.report import format_verdict, merge_verdicts
from sin_code_oracle.verdict import Verdict, VerdictStatus, Issue

# Format
v = Verdict(status=VerdictStatus.FAIL, summary="2 issues", issues=[
    Issue(verifier="security", severity="high", message="eval()", file="x.py", line=10),
])
print(format_verdict(v))

# Merge
merged = merge_verdicts([security_v, perf_v, style_v])
print(merged.status)  # worst of the three
```

## Caveats / footguns

- **`dict.update` on diagnostics can silently overwrite keys** from earlier verifiers. If you write per-verifier diagnostics, namespace them (e.g. `{"bandit": [...], "ruff": [...]}`).
- **`format_verdict` truncates nothing.** A verdict with 10,000 issues produces a 10,000-line string.
