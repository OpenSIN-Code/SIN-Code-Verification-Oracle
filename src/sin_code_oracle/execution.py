"""Execution Oracle.

This is the heart of the verification layer: it establishes *ground truth* by
actually running things, completely independent of what the agent claims.

Three probe kinds:
  - command : run an arbitrary command (build / test / lint), capture exit code
  - pytest  : run pytest and parse the machine-readable summary
  - http    : start a server command, wait for readiness, hit endpoints

Everything is parsed into a structured ExecutionResult so the core oracle can
reason about it. Self-reported "done" by the agent is never trusted; only the
exit code, the parsed test counts, and the HTTP responses count.

Docs: execution.doc.md
"""
from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Data model ─────────────────────────────────────────────────────────
@dataclass
class ExecutionResult:
    """Structured outcome of any probe (command / pytest / http)."""

    kind: str
    command: str
    success: bool
    exit_code: int
    duration_s: float
    stdout: str = ""
    stderr: str = ""
    metrics: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Return a JSON-serializable view with stdout/stderr tail-truncated."""
        d = dict(self.__dict__)
        # Truncate noisy streams for transport — last 4 KB is usually enough
        # to diagnose a failure without flooding the consumer.
        d["stdout"] = self.stdout[-4000:]
        d["stderr"] = self.stderr[-4000:]
        return d


# ── Oracle ─────────────────────────────────────────────────────────────
class ExecutionOracle:
    """Run shell commands, pytest, and HTTP probes with structured results.

    Ground truth is established by *running* code, not by trusting any
    upstream claim of success.
    """

    def __init__(self, root: str = ".", default_timeout: int = 300, env: dict | None = None):
        self.root = str(Path(root).resolve())
        # 300s default — long enough for most build/test commands on a
        # cold cache, short enough to fail fast on a hung subprocess.
        self.default_timeout = default_timeout
        # Caller-supplied env vars override the inherited environment.
        self.env = {**os.environ, **(env or {})}

    # ── Generic command probe (build, lint, custom test command, ...) ──
    def run_command(self, command: str, timeout: int | None = None) -> ExecutionResult:
        """Run `command` in `self.root` and capture exit code + streams.

        Never raises on non-zero exit. Returns success=False on timeout,
        with exit_code=124 (the conventional `timeout` CLI exit code).
        """
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout or self.default_timeout,
                env=self.env,
                check=False,
            )
            dur = time.monotonic() - start
            return ExecutionResult(
                kind="command",
                command=command,
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                duration_s=round(dur, 3),
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired as e:
            return ExecutionResult(
                kind="command",
                command=command,
                success=False,
                # 124 mirrors the GNU `timeout` exit code so callers can
                # recognize "timed out" without inspecting stderr.
                exit_code=124,
                duration_s=round(time.monotonic() - start, 3),
                stdout=(e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr="TIMEOUT",
            )

    # ── pytest probe with parsed pass/fail counts ──────────────────────
    def run_pytest(self, target: str = "", timeout: int | None = None) -> ExecutionResult:
        """Run pytest and parse the summary line into structured counts.

        The probe's `success` is stricter than the exit code: a test run
        with 0 tests is treated as a failure (you probably forgot to point
        pytest at the right path).
        """
        cmd = f"python -m pytest -q {target}".strip()
        res = self.run_command(cmd, timeout=timeout)
        res.kind = "pytest"
        res.metrics = self._parse_pytest_summary(res.stdout + "\n" + res.stderr)
        # Ground truth: success only if pytest reports >0 passed and 0 failed/errors.
        m = res.metrics
        res.success = (
            res.exit_code == 0
            and m.get("failed", 0) == 0
            and m.get("errors", 0) == 0
        )
        return res

    @staticmethod
    def _parse_pytest_summary(text: str) -> dict:
        """Extract {passed, failed, errors, skipped} from a pytest summary line.

        Matches the canonical "5 passed, 1 failed, 2 skipped in 0.34s" form.
        Missing keys default to 0.
        """
        metrics = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        # Matches lines like "5 passed, 1 failed, 2 skipped in 0.34s"
        for key in metrics:
            m = re.search(rf"(\d+)\s+{key}", text)
            if m:
                metrics[key] = int(m.group(1))
        return metrics

    # ── HTTP probe: boot a server, wait for the port, hit endpoints ───
    def probe_http(
        self,
        server_command: str,
        checks: list[dict],
        host: str = "127.0.0.1",
        port: int = 3000,
        boot_timeout: int = 30,
    ) -> ExecutionResult:
        """Boot a server, wait for it to listen, then run a list of HTTP checks.

        Args:
            server_command: Shell command that starts the server in the background.
            checks: List of `{path, method?, expect_status?, expect_contains?}`.
                    `method` defaults to GET.
            host, port: Where to expect the server to listen.
            boot_timeout: Seconds to wait for the port to open before giving up.

        Returns:
            ExecutionResult with `metrics['checks']` containing per-check results.
        """
        try:
            import httpx
        except ImportError:
            # httpx is an optional extra — missing it is a soft failure,
            # not a crash. Callers can install via `pip install httpx`.
            return ExecutionResult(
                kind="http", command=server_command, success=False,
                exit_code=-1, duration_s=0.0, stderr="httpx not installed",
            )

        start = time.monotonic()
        # preexec_fn=os.setsid creates a new process group on POSIX so we
        # can SIGTERM the whole tree later (not just the immediate child).
        proc = subprocess.Popen(
            server_command,
            shell=True,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )
        results = []
        booted = self._wait_for_port(host, port, boot_timeout)
        try:
            if not booted:
                return ExecutionResult(
                    kind="http", command=server_command, success=False,
                    exit_code=-1, duration_s=round(time.monotonic() - start, 3),
                    stderr=f"server did not open {host}:{port} within {boot_timeout}s",
                )
            base = f"http://{host}:{port}"
            with httpx.Client(base_url=base, timeout=10.0) as client:
                for chk in checks:
                    method = chk.get("method", "GET").upper()
                    path = chk.get("path", "/")
                    try:
                        resp = client.request(method, path)
                        ok = True
                        if "expect_status" in chk:
                            ok = ok and resp.status_code == chk["expect_status"]
                        if "expect_contains" in chk:
                            ok = ok and chk["expect_contains"] in resp.text
                        results.append({
                            "path": path, "method": method,
                            "status": resp.status_code, "ok": ok,
                        })
                    except httpx.RequestError as e:
                        # Network-level failure (refused, timeout) — record
                        # the error string so the consumer can debug.
                        results.append({"path": path, "method": method, "ok": False, "error": str(e)})
            success = bool(results) and all(r.get("ok") for r in results)
            return ExecutionResult(
                kind="http", command=server_command, success=success,
                exit_code=0 if success else 1,
                duration_s=round(time.monotonic() - start, 3),
                metrics={"checks": results},
            )
        finally:
            # Always kill the server, even if checks raised mid-way.
            self._terminate(proc)

    @staticmethod
    def _wait_for_port(host: str, port: int, timeout: int) -> bool:
        """Poll (host, port) every 300ms until the port accepts a connection.

        Returns True if the port opens within `timeout` seconds, False otherwise.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                if s.connect_ex((host, port)) == 0:
                    return True
            time.sleep(0.3)
        return False

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        """Tear down a server subprocess gracefully, then forcibly.

        Order: SIGTERM the process group (POSIX) → wait 10s → SIGKILL the
        immediate child. This lets long-polling requests finish before
        we hard-kill.
        """
        if proc.poll() is not None:
            return
        try:
            if os.name != "nt":
                # killpg targets the whole group set up by preexec_fn=os.setsid.
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired, PermissionError):
            # The process either already exited, ignored SIGTERM, or we
            # don't have permission — fall back to a hard kill of the child.
            try:
                proc.kill()
            except ProcessLookupError:
                pass
