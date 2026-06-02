# `correctness.py` — Correctness Verifier

What this file does: runs property-based smoke tests and compile checks using hypothesis.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `verify_correctness(code=None, path=None)` → Verdict

## Notes

Generates random inputs based on type hints. Returns `PASS` if the function handles all samples without crashing.
