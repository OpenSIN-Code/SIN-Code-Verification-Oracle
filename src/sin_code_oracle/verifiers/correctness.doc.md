# `correctness.py` — Correctness Verifier

What this file does: runs a synthesized test file (Hypothesis property-based smoke tests + a basic `compile()` check) against the user's code and returns a `Verdict`.

## Dependency map

- Imports: `verdict.py`, `runner.py`, stdlib (`sys`, `tempfile`, `os`, `pathlib`).
- External dep (optional): `hypothesis` — if missing, the compile check still runs but property tests are skipped (WARN).
- Imported by: `oracle.py` (called from `verify()` and `verify_file()`).

## Public API

| Function                                       | Purpose                                                                |
|------------------------------------------------|------------------------------------------------------------------------|
| `verify_correctness(code=None, path=None)`     | Generate a test file, run it, parse stdout for the pass/fail sentinel  |

## How it works

1. Build a Python test file by interpolating `code` into `_CORRECTNESS_TEST_TEMPLATE`.
2. The template imports Hypothesis (if available), defines the user's code, runs two auto-generated property-based tests (factorial, sort) when the source mentions those names, and finally calls `compile()` on the code.
3. The generated file prints `CORRECTNESS_PASS` on success, or `HYPOTHESIS_MISSING` if Hypothesis isn't installed.
4. The verifier checks stdout for these sentinels and returns the appropriate Verdict.

## Important config / limits

- **Hypothesis threshold values: `max_examples=5`, `deadline=5000`ms.** Five examples per property is enough to catch common bugs without slowing the verifier; 5s deadline accommodates slow CI.
- **Template is interpolation, not AST.** The user's code is injected via `.format()`. A snippet that contains a literal `{` or `}` will break the format. Workaround: use `path=` with a file instead.
- **Property tests are gated by name match.** `factorial` triggers the factorial test, `sort`/`sorted` triggers the sort test. Other functions are not auto-tested.
- **30s subprocess timeout.** Hypothesis is given up to 5s per test; with 2 tests max, 30s leaves generous margin.
- **Stderr truncated to 500 chars** in the Issue message. Full stderr is still in the runner's logs.

## Design decisions

- **Why synthesize a test file instead of importing the user's code?** Importing would mutate the caller's process state. A subprocess is hermetic — failures stay in the subprocess.
- **Why only factorial and sort as auto-tests?** They're the canonical examples for property-based testing: one is numeric + recursive, the other is order-related. Adding more would explode the template.
- **Why `compile()` as the always-on check?** It catches syntax errors before any test runs, and it works even when Hypothesis is missing.
- **Why substring-match sentinels in stdout?** It's the simplest IPC for "did the test file print this exact thing?". A structured return value would require either pickling or a JSON sidecar file.

## Usage example

```python
from sin_code_oracle.verifiers.correctness import verify_correctness

# A code snippet
v = verify_correctness(code="def factorial(n):\n    return n * factorial(n - 1) if n else 1\n")
print(v.status)  # probably FAIL (RecursionError or assertion)

# A file
v = verify_correctness(path="src/my_module.py")
print(v.summary)
```

## Caveats / footguns

- **The template uses `.format()`.** A snippet with literal `{` or `}` in it will raise `KeyError` or `IndexError` during template formatting. Use `path=` for untrusted code.
- **Property tests run in the subprocess, not in-process.** They can't import modules from the verifier's Python path; they only see what's in the synthesized test file.
- **Hypothesis version drift.** The test uses `st.integers(min_value=0, max_value=20)` which has been stable since Hypothesis 4.x. If a major rewrite of Hypothesis' API happens, the verifier will break silently (it'll just print `HYPOTHESIS_MISSING` on import error).
- **The synthesized test file imports hypothesis as `from hypothesis import given, settings, strategies as st`**. If the user has a different hypothesis API, the test will fail with a regular Python ImportError, not a graceful "missing optional".
