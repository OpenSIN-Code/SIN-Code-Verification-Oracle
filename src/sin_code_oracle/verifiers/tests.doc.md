# `tests.py` — Test Execution Verifier

What this file does: runs the user's test suite (defaulting to `pytest`) in a subprocess and parses the output for failure counts. Returns a `Verdict` with PASS / WARN / FAIL status.

## Dependency map

- Imports: `verdict.py`, `runner.py`, stdlib (`os`, `pathlib`).
- External tool: `pytest` (or whatever `test_command` points at).
- Imported by: `oracle.py` (called from `verify()` and `verify_directory()`).

## Public API

| Function                                                 | Purpose                                                       |
|----------------------------------------------------------|---------------------------------------------------------------|
| `verify_tests(test_command=None, cwd=".")`               | Run tests, parse failure count, return a Verdict              |

## Important config / limits

- **Default timeout: 120s.** A full pytest run on a mid-size project usually finishes well under this; tune via `test_command` if you need longer.
- **Default command: `["pytest"]`.** Pass a string (`"pytest -x"`) to split on whitespace, or an argv list (`["pytest", "-x"]`) to avoid shell escaping.
- **Pytest exit code 5 = no tests collected.** This is treated as PASS here, on the theory that "no tests" isn't a regression. The summary string still includes the returncode so consumers can distinguish.
- **Failure parsing is a regex-free integer scan.** We look for any line containing "failed" and take the first integer off it. Crude but version-stable.
- **Missing pytest = WARN Verdict**, not FAIL. The verifier degrades gracefully so a missing test runner doesn't sink the whole oracle.
- **`Issue.details` includes 2 KB tails of stdout and stderr.** Useful for debugging without re-running the suite.

## Design decisions

- **Why a subprocess and not an in-process pytest run?** Tests can have side effects (DB, network, filesystem). A subprocess is hermetic — the verifier can't be polluted by the tests it's running.
- **Why "any integer on a 'failed' line" instead of a proper regex?** Pytest's summary line is the canonical output, but plugin output (e.g. `pytest-cov`, `pytest-xdist`) can prefix or reformat it. A simple integer scan survives that noise.
- **Why exit code 5 is PASS?** Exit 5 means "you asked me to run tests, I found none." That's not a regression; it's a configuration problem the consumer can spot from the summary.
- **Why not parse JUnit XML?** JUnit is the cleanest format, but it requires pytest to be configured to produce it. The current approach works for the default config.

## Usage example

```python
from sin_code_oracle.verifiers.tests import verify_tests

# Default: just run pytest
v = verify_tests(cwd="/path/to/project")
print(v.summary)  # "Tests: 0 failure(s), returncode=0"

# Custom command
v = verify_tests(test_command="pytest -x -k smoke", cwd=".")
```

## Caveats / footguns

- **`test_command="pytest -x"` is shell-split.** This is safe because the result is passed to `subprocess.run` as argv, NOT to a shell. But the split is naive (whitespace-only) — quoted arguments like `'pytest "my test.py"'` will be broken.
- **The integer scan can miscount** if a test name contains a number and appears in a "failed" line. Rare in practice, but possible.
- **`details` may include secrets** in pytest output (e.g. a test that prints an API key). Sanitize before logging if the workspace is sensitive.
- **The verifier does NOT install pytest for you.** If it's missing, the Verdict is WARN — fix the env, then re-run.
