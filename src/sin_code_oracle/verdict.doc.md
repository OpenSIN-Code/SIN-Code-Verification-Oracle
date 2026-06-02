# verdict.py

What: Data models for verification results — `VerdictStatus`, `Issue`, and `Verdict`.

## Dependency map

- Used by every verifier module and `oracle.py`
- Imported by `report.py` for formatting and merging
- Re-exported in `__init__.py` so users can `from sin_code_oracle import Verdict, VerdictStatus`

## Key config / limits

- `VerdictStatus` order: PASS < WARN < FAIL < ERROR
- `Verdict.from_issues()` automatically determines status based on highest severity found

## Usage example

```python
from sin_code_oracle.verdict import Verdict, VerdictStatus, Issue

v = Verdict.from_issues(
    [Issue(verifier="style", severity="medium", message="line too long")]
)
print(v.status)  # WARN
```

## Caveats

- `to_json()` uses standard json.dumps; no custom serialization for complex objects.
