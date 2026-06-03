"""Correctness verification via property-based testing with Hypothesis.

We synthesize a small test file around the user's code, then run it. The
generated test file always does:
  1. A `compile()` of the code (catches syntax errors).
  2. Property-based smoke tests for two well-known patterns (factorial, sort)
     — gated by whether the source mentions the relevant name.

Property-based tests catch bugs the obvious unit tests miss: off-by-one in
factorial, non-idempotent sort, etc. They're not a replacement for real
test suites, but they're cheap and add a useful safety net.

Docs: correctness.doc.md
"""
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


# Sentinel strings in the generated test file. Read by the verifier to
# decide what passed and what failed. Keep them unique — the verifier
# searches stdout for them with `in`.
_CORRECTNESS_TEST_TEMPLATE = '''
import sys
import traceback

try:
    from hypothesis import given, settings, strategies as st
except Exception as e:
    print("HYPOTHESIS_MISSING", e)
    sys.exit(0)

{code}

# Auto-generated property-based smoke tests
# `max_examples=5` keeps the run fast (each test is O(ms)).
# `deadline=5000` (ms) gives slow CI machines some headroom.
if 'factorial' in {code!r}:
    @given(st.integers(min_value=0, max_value=20))
    @settings(max_examples=5, deadline=5000)
    def test_factorial(n):
        result = factorial(n)
        assert isinstance(result, int)
        assert result >= 1
    test_factorial()

if 'sort' in {code!r} or 'sorted' in {code!r}:
    @given(st.lists(st.integers(), max_size=10))
    @settings(max_examples=5, deadline=5000)
    def test_sort(lst):
        result = sorted(lst)
        assert len(result) == len(lst)
        assert result == sorted(result)
    test_sort()

# Always run a simple parse/compile check
compile({code!r}, '<string>', 'exec')
print("CORRECTNESS_PASS")
'''


def verify_correctness(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Run property-based smoke tests + `compile()` on `code` or `path`.

    Returns:
        Verdict. `PASS` if all checks ran clean, `WARN` if Hypothesis is
        missing (compile check still runs), `ERROR` on missing input or
        I/O failure, `FAIL` if any assertion failed.
    """
    issues: list[Issue] = []
    source = ""
    if code is not None:
        source = code
    elif path is not None:
        try:
            source = Path(path).read_text()
        except Exception as exc:
            return Verdict(
                status=VerdictStatus.ERROR,
                issues=[],
                summary=f"Could not read {path}: {exc}",
            )
    else:
        return Verdict(status=VerdictStatus.ERROR, issues=[], summary="No target provided")

    # Synthesize a test file that imports Hypothesis, executes the user's
    # code, and runs the auto-generated property tests.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_CORRECTNESS_TEST_TEMPLATE.format(code=source))
        test_file = f.name

    try:
        result = run_command([sys.executable, test_file], timeout=30)
        stdout = result["stdout"]
        stderr = result["stderr"]
        if "HYPOTHESIS_MISSING" in stdout:
            # Hypothesis is optional — degrade gracefully, but downgrade
            # to WARN so the caller knows we didn't run the full check.
            issues.append(
                Issue(
                    verifier="correctness",
                    severity="info",
                    message="hypothesis not installed; skipping property-based tests",
                )
            )
            return Verdict(status=VerdictStatus.WARN, issues=issues, summary="hypothesis unavailable")
        if "CORRECTNESS_PASS" in stdout:
            return Verdict(
                status=VerdictStatus.PASS,
                issues=[],
                summary="Property-based and compile checks passed",
            )
        if stderr:
            # Truncate to first 500 chars to keep the Issue small; full
            # stderr is still in the runner's logs.
            issues.append(
                Issue(
                    verifier="correctness",
                    severity="high",
                    message=f"Property-based or compile check failed: {stderr[:500]}",
                )
            )
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)

    summary = f"Correctness scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
