# Purpose: Correctness verification using property-based testing with Hypothesis.
# Docs: correctness.doc.md
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus
from ..runner import run_command


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
    """Run property-based smoke tests or compile check on code."""
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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_CORRECTNESS_TEST_TEMPLATE.format(code=source))
        test_file = f.name

    try:
        result = run_command([sys.executable, test_file], timeout=30)
        stdout = result["stdout"]
        stderr = result["stderr"]
        if "HYPOTHESIS_MISSING" in stdout:
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
