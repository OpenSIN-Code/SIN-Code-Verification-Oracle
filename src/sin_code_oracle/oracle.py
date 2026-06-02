# Purpose: Main VerificationOracle class that orchestrates all verifiers.
# Docs: oracle.doc.md
import tempfile
import os
from pathlib import Path
from typing import Any

from .verdict import Verdict, VerdictStatus
from .report import merge_verdicts
from .verifiers import verify_security, verify_performance, verify_correctness, verify_style, verify_tests


class VerificationOracle:
    """Orchestrate security, performance, correctness, style, and test verification."""

    def __init__(self, workspace: str | Path = "."):
        self.workspace = Path(workspace).resolve()

    def verify(
        self,
        code: str | None = None,
        language: str = "python",
        test_command: str | None = None,
        run_diagnostics: bool = True,
    ) -> Verdict:
        """Run the full verification suite.

        Returns a Verdict with status (PASS/FAIL/WARN), issues, summary, and diagnostics.
        """
        if language != "python":
            return Verdict(
                status=VerdictStatus.WARN,
                issues=[],
                summary=f"Language '{language}' not fully supported; limited checks applied",
            )

        verdicts: list[Verdict] = []
        temp_path = None
        if code is not None:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=self.workspace) as f:
                f.write(code)
                temp_path = f.name

        try:
            # Security
            if code is not None:
                verdicts.append(verify_security(code=code))
            else:
                verdicts.append(verify_security(path=self.workspace))

            # Performance
            if code is not None:
                verdicts.append(verify_performance(code=code))
            elif temp_path:
                verdicts.append(verify_performance(path=temp_path))
            else:
                verdicts.append(verify_performance(path=self.workspace))

            # Correctness
            if code is not None:
                verdicts.append(verify_correctness(code=code))
            elif temp_path:
                verdicts.append(verify_correctness(path=temp_path))
            else:
                verdicts.append(verify_correctness(path=self.workspace))

            # Style
            if code is not None:
                verdicts.append(verify_style(code=code))
            elif temp_path:
                verdicts.append(verify_style(path=temp_path))
            else:
                verdicts.append(verify_style(path=self.workspace))

            # Tests
            if test_command is not None:
                verdicts.append(verify_tests(test_command=test_command, cwd=self.workspace))
            elif code is not None:
                # No tests to run for a single code snippet unless explicitly provided
                verdicts.append(
                    Verdict(
                        status=VerdictStatus.PASS,
                        issues=[],
                        summary="No test_command provided for code snippet",
                    )
                )
            else:
                verdicts.append(verify_tests(cwd=self.workspace))
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

        merged = merge_verdicts(verdicts)
        if not run_diagnostics:
            merged.diagnostics = {}
        return merged

    def verify_file(self, path: str) -> Verdict:
        """Verify a single file."""
        target = Path(path).resolve()
        if not target.exists():
            return Verdict(
                status=VerdictStatus.ERROR,
                issues=[],
                summary=f"File not found: {target}",
            )
        verdicts: list[Verdict] = [
            verify_security(path=target),
            verify_performance(path=target),
            verify_correctness(path=target),
            verify_style(path=target),
        ]
        return merge_verdicts(verdicts)

    def verify_directory(self, path: str) -> list[Verdict]:
        """Verify all Python files in a directory."""
        target = Path(path).resolve()
        if not target.is_dir():
            return [
                Verdict(
                    status=VerdictStatus.ERROR,
                    issues=[],
                    summary=f"Directory not found: {target}",
                )
            ]
        results: list[Verdict] = []
        for file in target.rglob("*.py"):
            results.append(self.verify_file(str(file)))
        return results
