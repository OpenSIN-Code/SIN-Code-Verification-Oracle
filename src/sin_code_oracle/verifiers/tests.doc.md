# `tests.py` — Test Verifier

What this file does: runs isolated pytest execution with timeout.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `verify_tests(test_command=None, cwd=None)` → Verdict

## Notes

Default timeout is 60 seconds. Returns `FAIL` if any test fails or times out.
