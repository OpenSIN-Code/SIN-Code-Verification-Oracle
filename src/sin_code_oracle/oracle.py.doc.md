# oracle.py

What: Main orchestrator class `VerificationOracle` that runs all verification strategies and returns a merged `Verdict`.

## Dependency map

- Imports `verdict.py` for data models
- Imports `report.py` for `merge_verdicts`
- Imports all modules under `verifiers/` (security, performance, correctness, style, tests)
- Used by `__init__.py` (re-exported as `from sin_code_oracle import VerificationOracle`)
- Called by examples and user scripts

## Key config / limits

- `workspace` defaults to current directory (`.`)
- Temporary files are created in `workspace` for code snippets so that relative imports and style checks work consistently
- `run_diagnostics=False` strips the `diagnostics` dict from the final merged Verdict

## Design decisions

- Why temporary file in `workspace`? So ruff/bandit see the same relative path context as real workspace files.
- Why merge with `report.merge_verdicts`? Each verifier is independent; merging isolates failure domains.

## Usage example

```python
oracle = VerificationOracle(workspace=".")
v = oracle.verify(code="def foo(): return 42", language="python")
print(v.status)  # PASS or WARN
```

## Caveats

- Only Python is fully supported; other languages return a WARN Verdict.
- `verify_directory` runs each file independently — no cross-file analysis yet.
