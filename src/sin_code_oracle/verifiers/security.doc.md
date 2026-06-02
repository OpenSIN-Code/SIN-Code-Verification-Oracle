# `security.py` — Security Verifier

What this file does: checks for hardcoded secrets, unsafe eval, SQL injection, and other security issues using bandit.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `verify_security(code=None, path=None)` → Verdict

## Notes

Returns `PASS` if no issues found, `FAIL` with issues list otherwise.
