# `style.py` — Style Verifier

What this file does: checks lint, import order, and formatting using ruff.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `verify_style(code=None, path=None)` → Verdict

## Notes

Runs `ruff check` and `ruff format --check`. Returns `PASS` if no style violations.
