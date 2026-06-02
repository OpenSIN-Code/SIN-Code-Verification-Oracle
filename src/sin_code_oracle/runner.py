# Purpose: Subprocess runner with isolation and timeout for verification commands.
# Docs: runner.doc.md
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Any


def run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
) -> dict[str, Any]:
    """Run a command in an isolated subprocess with timeout.

    Returns dict with returncode, stdout, stderr, and timed_out flag.
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


def run_in_temp_file(code: str, suffix: str = ".py") -> dict[str, Any]:
    """Write code to a temporary file and run it with python.

    Returns the run_command result dict.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(code)
        path = f.name
    try:
        return run_command(["python", path], cwd=os.path.dirname(path))
    finally:
        os.unlink(path)
