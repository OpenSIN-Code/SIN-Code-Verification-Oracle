"""Diagnostics Oracle.

Instead of re-implementing a weaker AST analyzer, we treat the *existing*
language servers / compilers / linters as ground-truth oracles. This is the
cheapest and strongest correctness signal available, and it is exactly what
is missing from a tree-sitter-only stack.

Each provider:
  - declares which file extensions it covers,
  - detects whether its underlying tool is installed (graceful degradation),
  - shells out and parses the tool's machine-readable output into Diagnostic.

Adding a language = adding a Provider. No core changes required.

Docs: diagnostics.doc.md
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ── Data models ────────────────────────────────────────────────────────
@dataclass
class Diagnostic:
    """A single normalized finding from any language tool.

    Fields are deliberately tool-agnostic so providers can be swapped without
    touching consumers.
    """

    file: str
    line: int
    column: int
    severity: str  # "error" | "warning" | "info"
    message: str
    code: str | None = None
    source: str | None = None  # which tool produced it

    def as_dict(self) -> dict:
        """Return a JSON-serializable view of this Diagnostic."""
        return self.__dict__


@dataclass
class DiagnosticsReport:
    """Aggregated output from a DiagnosticsOracle.check() call.

    Tracks which tools were probed, which were missing, and the union of
    all findings (normalized to `Diagnostic`).
    """

    available_tools: list[str] = field(default_factory=list)
    missing_tools: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Number of findings with severity == 'error'."""
        return sum(1 for d in self.diagnostics if d.severity == "error")

    @property
    def warning_count(self) -> int:
        """Number of findings with severity == 'warning'."""
        return sum(1 for d in self.diagnostics if d.severity == "warning")

    def as_dict(self) -> dict:
        """Return a JSON-serializable view of this report (incl. counts)."""
        return {
            "available_tools": self.available_tools,
            "missing_tools": self.missing_tools,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
        }


# ── Helpers ────────────────────────────────────────────────────────────
def _run(cmd: list[str], cwd: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Subprocess helper that captures both streams in text mode.

    Never raises on non-zero exit — callers inspect `returncode` themselves.
    Default 120s timeout is intentionally generous: pyright on a large repo
    can take a while on first run.
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ── Providers ──────────────────────────────────────────────────────────
class DiagnosticProvider:
    """Base class. Override `tool`, `extensions`, `run`."""

    name: str = "base"
    tool: str = ""  # executable name probed with shutil.which
    extensions: tuple[str, ...] = ()

    def available(self) -> bool:
        """True iff the underlying CLI tool is on PATH."""
        return bool(self.tool) and shutil.which(self.tool) is not None

    def covers(self, files: list[str]) -> bool:
        """True iff at least one of `files` matches this provider's extensions."""
        return any(f.endswith(self.extensions) for f in files)

    def run(self, root: str, files: list[str]) -> list[Diagnostic]:  # pragma: no cover
        """Run the provider and return a list of normalized findings."""
        raise NotImplementedError


class PyrightProvider(DiagnosticProvider):
    """Python type checking via `pyright --outputjson`.

    Pyright is treated as the strongest static Python signal — see
    https://github.com/microsoft/pyright for the JSON schema we parse.
    """

    name = "pyright"
    tool = "pyright"
    extensions = (".py",)

    def run(self, root: str, files: list[str]) -> list[Diagnostic]:
        proc = _run([self.tool, "--outputjson", root], cwd=root)
        out: list[Diagnostic] = []
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            # Empty / malformed stdout → no findings. Never raise from a provider.
            return out
        # Pyright uses "information" for hints — we map it to "info".
        sev_map = {"error": "error", "warning": "warning", "information": "info"}
        for d in data.get("generalDiagnostics", []):
            rng = d.get("range", {}).get("start", {})
            # pyright uses 0-based lines/cols; we expose 1-based everywhere.
            out.append(
                Diagnostic(
                    file=d.get("file", ""),
                    line=rng.get("line", 0) + 1,
                    column=rng.get("character", 0) + 1,
                    severity=sev_map.get(d.get("severity", "error"), "error"),
                    message=d.get("message", ""),
                    code=str(d.get("rule")) if d.get("rule") else None,
                    source="pyright",
                )
            )
        return out


class RuffProvider(DiagnosticProvider):
    """Fast Python linting via `ruff check --output-format=json`."""

    name = "ruff"
    tool = "ruff"
    extensions = (".py",)

    def run(self, root: str, files: list[str]) -> list[Diagnostic]:
        proc = _run([self.tool, "check", "--output-format=json", root], cwd=root)
        out: list[Diagnostic] = []
        try:
            data = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            return out
        for d in data:
            loc = d.get("location", {})
            # ruff reports rows 1-based; we keep that convention.
            out.append(
                Diagnostic(
                    file=d.get("filename", ""),
                    line=loc.get("row", 0),
                    column=loc.get("column", 0),
                    severity="warning",
                    message=d.get("message", ""),
                    code=d.get("code"),
                    source="ruff",
                )
            )
        return out


class TscProvider(DiagnosticProvider):
    """TypeScript type checking via `tsc --noEmit --pretty false`.

    Output is plain text — we regex-parse `path(line,col): error TSxxxx: msg`.
    """

    name = "tsc"
    tool = "tsc"
    extensions = (".ts", ".tsx")

    def run(self, root: str, files: list[str]) -> list[Diagnostic]:
        proc = _run([self.tool, "--noEmit", "--pretty", "false"], cwd=root)
        out: list[Diagnostic] = []
        # Format: path(line,col): error TSxxxx: message
        for line in (proc.stdout + proc.stderr).splitlines():
            if "): error TS" not in line and "): warning TS" not in line:
                continue
            try:
                loc_part, rest = line.split("): ", 1)
                path, pos = loc_part.rsplit("(", 1)
                ln, col = pos.split(",")
                sev, rest2 = rest.split(" ", 1)
                code, message = rest2.split(":", 1)
                out.append(
                    Diagnostic(
                        file=path.strip(),
                        line=int(ln),
                        column=int(col),
                        severity="error" if sev == "error" else "warning",
                        message=message.strip(),
                        code=code.strip(),
                        source="tsc",
                    )
                )
            except (ValueError, IndexError):
                # Malformed tsc line — skip it. Don't crash the provider.
                continue
        return out


# ── Oracle ─────────────────────────────────────────────────────────────
class DiagnosticsOracle:
    """Runs every applicable, installed provider and aggregates results.

    Adding a language is a one-class change: subclass `DiagnosticProvider`
    and pass it via the `providers` constructor argument.
    """

    def __init__(self, providers: list[DiagnosticProvider] | None = None):
        # Default set: pyright (types) + ruff (lint) + tsc (TS).
        # All three are graceful-degradation: missing tools produce no
        # findings, they don't fail the whole check.
        self.providers = providers or [
            PyrightProvider(),
            RuffProvider(),
            TscProvider(),
        ]

    def check(self, root: str, changed_files: list[str] | None = None) -> DiagnosticsReport:
        """Run every applicable provider against `root` (or a subset of files).

        Args:
            root: Project root to scan.
            changed_files: If provided, only providers covering these files run.
                           Useful for incremental checks during agent edits.

        Returns:
            DiagnosticsReport with `available_tools`, `missing_tools`, and
            the union of all `diagnostics`.
        """
        root = str(Path(root).resolve())
        # Without an explicit file list, walk the whole tree. This is
        # expensive on big repos — callers that already have a file list
        # should pass it via `changed_files`.
        files = changed_files or [
            str(p) for p in Path(root).rglob("*") if p.is_file()
        ]
        report = DiagnosticsReport()
        for provider in self.providers:
            if not provider.covers(files):
                continue
            if not provider.available():
                report.missing_tools.append(provider.tool)
                continue
            report.available_tools.append(provider.name)
            try:
                report.diagnostics.extend(provider.run(root, files))
            except (subprocess.TimeoutExpired, OSError):
                # A provider crashing must never crash the oracle — record
                # it as a missing tool and continue with the next provider.
                report.missing_tools.append(f"{provider.tool} (errored)")
        return report
