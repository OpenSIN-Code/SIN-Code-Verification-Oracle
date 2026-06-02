# `oracle.py` — Verification Oracle

What this file does: orchestrates security, performance, correctness, style, and test verification for Python code.

## Dependencies

- Imported by: `__init__.py`, tests, CLI, MCP server
- Imports: `verdict`, `report`, `verifiers` (security, performance, correctness, style, tests)

## Public API

- `VerificationOracle(workspace=".")` — main orchestrator
- `verify(code=None, language="python", test_command=None, run_diagnostics=True)` — run full verification suite
- `verify_file(path)` — verify a single file
- `verify_directory(path)` — verify all Python files in a directory

## Usage

```python
from sin_code_oracle import VerificationOracle
oracle = VerificationOracle(".")
verdict = oracle.verify(code="def foo(): return 42")
print(verdict.to_json())
```

## Notes

When `code` is provided, a temporary file is created in `workspace` and cleaned up after verification. Non-Python languages return a WARN verdict with limited checks.
