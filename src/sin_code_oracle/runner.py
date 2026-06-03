"""Subprocess runner with isolation and timeout for verification commands.

A thin convenience wrapper around `subprocess.run` that always returns a
dict (never raises) and adds a `timed_out` flag so callers don't have to
catch `TimeoutExpired` themselves.

Docs: runner.doc.md
"""
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from typing import Any


# ── Command runner ─────────────────────────────────────────────────────
def run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
) -> dict[str, Any]:
    """Run `cmd` in a subprocess with timeout, returning a structured result.

    Args:
        cmd: Argv list (do NOT pass a single shell string — use `shell=True`
             if you need that).
        cwd: Working directory for the subprocess.
        timeout: Seconds before declaring the run timed out.
        env: Extra env vars merged on top of the inherited environment.
        capture_output: When True, capture stdout+stderr (text mode).

    Returns:
        Dict with `returncode`, `stdout`, `stderr`, `timed_out`.
        - `returncode` is `-1` on timeout or missing command.
        - `timed_out=True` is set on `TimeoutExpired`.
        - On `FileNotFoundError`, `stderr` contains `"Command not found: <cmd[0]>"`.
    """
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        # `exc.stdout` / `exc.stderr` may be bytes or None — only decode
        # when bytes; otherwise the str passes through unchanged.
        return {
            "returncode": -1,
            "stdout": exc.stdout.decode() if exc.stdout else "",
            "stderr": exc.stderr.decode() if exc.stderr else "",
            "timed_out": True,
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command not found: {cmd[0]}",
            "timed_out": False,
        }


# ── Code snippet runner ────────────────────────────────────────────────
def run_in_temp_file(code: str, suffix: str = ".py") -> dict[str, Any]:
    """Write `code` to a temp file and run it with the current Python interpreter.

    Useful for the `correctness` verifier: it generates a synthetic test file
    and runs it to check property-based smoke tests + a basic `compile()`.

    The temp file is created in the system default temp dir and unlinked in
    a `finally` block, so a crash in the subprocess doesn't leak it.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(code)
        path = f.name
    try:
        # `sys.executable` is the interpreter that's currently running us —
        # never `python` on PATH, which could be a different version.
        return run_command([sys.executable, path], cwd=os.path.dirname(path))
    finally:
        os.unlink(path)
