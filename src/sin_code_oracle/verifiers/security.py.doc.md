# security.py

What: Security verification using Bandit (Python security linter) plus basic safety heuristics.

## Dependency map

- Uses `runner.run_command` to execute `bandit` in a subprocess
- Returns `Verdict` and `Issue` objects from `verdict.py`
- Called by `oracle.py` during `verify()` and `verify_file()`

## Key config / limits

- Bandit runs with `-ll` (medium/high severity) and `-ii` (medium/high confidence)
- JSON output is parsed to extract structured issues
- If `bandit` is not installed, returns a `WARN` Verdict with an info-level issue

## Design decisions

- Why subprocess instead of Python API? Bandit's CLI is stable and the JSON output is well-structured; the Python API changes more frequently.
- Why tempfile for code snippets? Bandit requires a file path to scan.

## Usage example

```python
from sin_code_oracle.verifiers.security import verify_security

v = verify_security(code='password = "secret"')
print(v.issues[0].message)  # hardcoded password detected
```

## Caveats

- Bandit must be installed separately or via `pip install sin-code-oracle[dev]`.
- Large code snippets may slow down the scan; timeout is 60 seconds.
