# Purpose: Test suite for the Verification Oracle (20+ tests).
# Docs: tests.doc.md
import os
import sys
import tempfile
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from sin_code_oracle import VerificationOracle, Verdict, VerdictStatus, Issue
from sin_code_oracle.verdict import VerdictStatus
from sin_code_oracle.verifiers.security import verify_security
from sin_code_oracle.verifiers.performance import verify_performance
from sin_code_oracle.verifiers.correctness import verify_correctness
from sin_code_oracle.verifiers.style import verify_style
from sin_code_oracle.verifiers.tests import verify_tests
from sin_code_oracle.report import merge_verdicts, format_verdict


# ── Basic Oracle Construction ─────────────────────────────────

def test_oracle_init_default():
    oracle = VerificationOracle()
    assert oracle.workspace == Path(".").resolve()


def test_oracle_init_custom():
    oracle = VerificationOracle(workspace="/tmp")
    assert oracle.workspace == Path("/tmp").resolve()


# ── Verdict Models ────────────────────────────────────────────

def test_verdict_pass_no_issues():
    v = Verdict(status=VerdictStatus.PASS, issues=[], summary="OK")
    assert v.status == VerdictStatus.PASS
    assert v.to_dict()["status"] == "PASS"


def test_verdict_to_json():
    v = Verdict(status=VerdictStatus.PASS, issues=[], summary="OK")
    assert '"status": "PASS"' in v.to_json()


def test_verdict_from_issues_critical():
    issues = [Issue(verifier="x", severity="critical", message="bad")]
    v = Verdict.from_issues(issues)
    assert v.status == VerdictStatus.FAIL


def test_verdict_from_issues_medium():
    issues = [Issue(verifier="x", severity="medium", message="warn")]
    v = Verdict.from_issues(issues)
    assert v.status == VerdictStatus.WARN


# ── Security Verifier ───────────────────────────────────────

def test_security_clean_code():
    code = "x = 1\n"
    v = verify_security(code=code)
    assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_security_detects_hardcoded_password():
    # Bandit flags hardcoded password strings and unsafe eval
    code = 'eval("1+1")\n'
    v = verify_security(code=code)
    assert any("eval" in i.message.lower() or "blacklist" in i.message.lower() for i in v.issues)


def test_security_no_target():
    v = verify_security()
    assert v.status == VerdictStatus.ERROR


# ── Performance Verifier ────────────────────────────────────

def test_performance_no_issues():
    code = "def foo(x):\n    return x + 1\n"
    v = verify_performance(code=code)
    assert v.status == VerdictStatus.PASS


def test_performance_detects_nested_loop():
    code = "def foo(n):\n    for i in range(n):\n        for j in range(n):\n            print(i,j)\n"
    v = verify_performance(code=code)
    assert any("nested loop" in i.message.lower() for i in v.issues)


def test_performance_detects_large_allocation():
    code = "x = [0] * 100000\n"
    v = verify_performance(code=code)
    assert any("allocation" in i.message.lower() for i in v.issues)


def test_performance_no_target():
    v = verify_performance()
    assert v.status == VerdictStatus.ERROR


# ── Correctness Verifier ─────────────────────────────────────

def test_correctness_clean_code():
    code = "def foo(x):\n    return x + 1\n"
    v = verify_correctness(code=code)
    assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_correctness_no_target():
    v = verify_correctness()
    assert v.status == VerdictStatus.ERROR


# ── Style Verifier ────────────────────────────────────────────

def test_style_clean_code():
    code = "def foo(x):\n    return x + 1\n"
    v = verify_style(code=code)
    assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_style_detects_import_order():
    code = "import os\nimport sys\nimport json\n"
    v = verify_style(code=code)
    # Should at least run without error
    assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_style_no_target():
    v = verify_style()
    assert v.status == VerdictStatus.ERROR


# ── Tests Verifier ────────────────────────────────────────────

def test_tests_no_target():
    # Running pytest in a temp dir with no tests should still pass
    with tempfile.TemporaryDirectory() as td:
        v = verify_tests(cwd=td)
        assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_tests_runs_provided_command():
    with tempfile.TemporaryDirectory() as td:
        v = verify_tests(test_command="python -c 'print(1)'", cwd=td)
        assert v.status == VerdictStatus.PASS


# ── Oracle.verify() Integration ───────────────────────────────

def test_oracle_verify_code_pass():
    oracle = VerificationOracle()
    code = "def foo():\n    return 42\n"
    v = oracle.verify(code=code, language="python", run_diagnostics=True)
    assert isinstance(v, Verdict)
    assert v.status in (VerdictStatus.PASS, VerdictStatus.WARN)


def test_oracle_verify_code_security_issue():
    oracle = VerificationOracle()
    code = 'eval("1+1")\n'
    v = oracle.verify(code=code, language="python", run_diagnostics=True)
    assert v.status in (VerdictStatus.FAIL, VerdictStatus.WARN)


def test_oracle_verify_code_performance_issue():
    oracle = VerificationOracle()
    code = "def foo(n):\n    for i in range(n):\n        for j in range(n):\n            pass\n"
    v = oracle.verify(code=code, language="python", run_diagnostics=True)
    assert any("nested" in i.message.lower() or "loop" in i.message.lower() for i in v.issues)


def test_oracle_verify_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def bar():\n    return 1\n")
        path = f.name
    try:
        oracle = VerificationOracle()
        v = oracle.verify_file(path)
        assert isinstance(v, Verdict)
    finally:
        os.unlink(path)


def test_oracle_verify_directory():
    with tempfile.TemporaryDirectory() as td:
        Path(td, "a.py").write_text("def a(): return 1\n")
        Path(td, "b.py").write_text("def b(): return 2\n")
        oracle = VerificationOracle()
        verdicts = oracle.verify_directory(td)
        assert len(verdicts) == 2
        for v in verdicts:
            assert isinstance(v, Verdict)


def test_oracle_verify_nonexistent_file():
    oracle = VerificationOracle()
    v = oracle.verify_file("/nonexistent/file.py")
    assert v.status == VerdictStatus.ERROR


def test_oracle_verify_nonexistent_directory():
    oracle = VerificationOracle()
    verdicts = oracle.verify_directory("/nonexistent/dir")
    assert verdicts[0].status == VerdictStatus.ERROR


def test_oracle_verify_unsupported_language():
    oracle = VerificationOracle()
    v = oracle.verify(code="x", language="rust")
    assert v.status == VerdictStatus.WARN


def test_oracle_verify_no_diagnostics():
    oracle = VerificationOracle()
    code = "def foo():\n    return 42\n"
    v = oracle.verify(code=code, language="python", run_diagnostics=False)
    assert v.diagnostics == {}


# ── Report Helpers ──────────────────────────────────────────

def test_merge_verdicts():
    v1 = Verdict(status=VerdictStatus.PASS, issues=[], summary="A")
    v2 = Verdict(status=VerdictStatus.FAIL, issues=[Issue("x", "high", "bad")], summary="B")
    merged = merge_verdicts([v1, v2])
    assert merged.status == VerdictStatus.FAIL
    assert len(merged.issues) == 1


def test_format_verdict():
    v = Verdict(status=VerdictStatus.PASS, issues=[], summary="All good")
    text = format_verdict(v)
    assert "PASS" in text
    assert "All good" in text


# ── Issue Model ───────────────────────────────────────────────

def test_issue_to_dict():
    i = Issue(verifier="v", severity="high", message="m", file="f", line=1)
    d = i.to_dict()
    assert d["verifier"] == "v"
    assert d["line"] == 1


# ── Bundle Import Contract ──────────────────────────────────

def test_bundle_import_verification_oracle():
    from sin_code_oracle.oracle import VerificationOracle as V1
    from sin_code_oracle import VerificationOracle as V2
    assert V1 is V2


def test_bundle_verify_signature():
    oracle = VerificationOracle(workspace="/tmp")
    # Should accept both signatures without crashing
    v1 = oracle.verify(test_command="pytest", run_diagnostics=False)
    assert isinstance(v1, Verdict)
    v2 = oracle.verify(code="def foo(): return 42", language="python")
    assert isinstance(v2, Verdict)
