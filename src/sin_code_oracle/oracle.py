"""Main VerificationOracle — orchestrates all verifiers.

The oracle is the public face of the package: callers (CLI, MCP server, agent
loops) construct a `VerificationOracle` and call `verify()` / `verify_file()` /
`verify_directory()`. Internally it fans out to the five verifier modules
(security, performance, correctness, style, tests) and merges their verdicts
into a single `Verdict` with the worst-case status.

Docs: oracle.doc.md
"""
import tempfile
import os
from pathlib import Path
from typing import Any

from .verdict import Verdict, VerdictStatus
from .report import merge_verdicts
from .verifiers import verify_security, verify_performance, verify_correctness, verify_style, verify_tests


# ── Orchestrator ───────────────────────────────────────────────────────
class VerificationOracle:
    """Orchestrate security, performance, correctness, style, and test verification.

    All three `verify_*` methods return structured `Verdict` objects — see
    `verdict.py` for the data model. Failures in any one verifier do NOT
    short-circuit the others; the final verdict is the worst-case across all.
    """

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

        Args:
            code: Optional Python source string. If provided, a temporary file
                  is created in `workspace` and all file-based verifiers run on it.
            language: Currently only "python" is fully supported; other languages
                      return a WARN Verdict with limited checks.
            test_command: Optional test command (e.g. "pytest -x"). If None and
                          `code` is provided, no test verifier runs.
            run_diagnostics: When False, the merged verdict's `diagnostics` dict
                             is stripped before returning.

        Returns:
            Verdict with status (PASS/FAIL/WARN/ERROR), issues, summary, and diagnostics.
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
            # Tempfile lives in `workspace` so relative paths inside the code
            # (and in tool output) match the context the agent was working in.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=self.workspace) as f:
                f.write(code)
                temp_path = f.name

        try:
            # ── Security ──
            if code is not None:
                verdicts.append(verify_security(code=code))
            else:
                verdicts.append(verify_security(path=self.workspace))

            # ── Performance ──
            if code is not None:
                verdicts.append(verify_performance(code=code))
            elif temp_path:
                verdicts.append(verify_performance(path=temp_path))
            else:
                verdicts.append(verify_performance(path=self.workspace))

            # ── Correctness ──
            if code is not None:
                verdicts.append(verify_correctness(code=code))
            elif temp_path:
                verdicts.append(verify_correctness(path=temp_path))
            else:
                verdicts.append(verify_correctness(path=self.workspace))

            # ── Style ──
            if code is not None:
                verdicts.append(verify_style(code=code))
            elif temp_path:
                verdicts.append(verify_style(path=temp_path))
            else:
                verdicts.append(verify_style(path=self.workspace))

            # ── Tests ──
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
            # Always clean up the temp file, even if a verifier crashed.
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

        merged = merge_verdicts(verdicts)
        if not run_diagnostics:
            # Diagnostics can be large (full bandit/ruff output); strip them
            # when the caller only wants the pass/fail signal.
            merged.diagnostics = {}
        return merged

    # ── Single-file / whole-directory convenience wrappers ─────────────
    def verify_file(self, path: str) -> Verdict:
        """Run security, performance, correctness, and style on a single file.

        Skips the test verifier (no test runner makes sense for one file).
        """
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
        """Verify every `.py` file under `path` (recursive).

        Returns a list of Verdicts — one per file. Files are processed
        sequentially; there is no cross-file analysis yet.
        """
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
