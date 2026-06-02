# `runner.py` — Test Runner

What this file does: lightweight subprocess runner for executing tests with timeouts and capture.

## Dependencies

- Imported by: `verifiers/tests.py`, tests

## Public API

- `run(command, cwd, timeout=60)` → `{returncode, stdout, stderr, duration}`

## Notes

Captures stdout/stderr as strings. Kills the process if timeout is exceeded.
