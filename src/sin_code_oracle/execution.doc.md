# `execution.py` — Execution Oracle

What this file does: the **ground-truth** layer of the verification stack. It runs shell commands, pytest, and HTTP probes in subprocesses and returns a structured `ExecutionResult` so downstream consumers (verdict merger, eval harness) can reason about success without parsing raw bytes.

## Dependency map

- Imports: stdlib only (`subprocess`, `socket`, `signal`, `os`, `re`, `time`, `dataclasses`, `pathlib`).
- Optional runtime dep: `httpx` — only required for `probe_http()`. Missing it returns a soft-fail `ExecutionResult`, never a crash.
- Imported by: `eval_harness.py` (per-task `run_command` calls), `runner.py` (legacy subprocess wrapper).

## Public API

| Symbol             | Purpose                                                                |
|--------------------|------------------------------------------------------------------------|
| `ExecutionResult`  | Structured outcome: kind, command, success, exit_code, duration, stdout/stderr, metrics |
| `ExecutionOracle`  | Orchestrator with three probe kinds (see below)                         |

### Probes

| Method            | What it does                                                | Returns success= when…                |
|-------------------|-------------------------------------------------------------|---------------------------------------|
| `run_command`     | Run an arbitrary shell command                              | exit_code == 0                        |
| `run_pytest`      | Run `python -m pytest -q <target>`, parse summary line      | exit_code == 0 AND 0 failed/errors    |
| `probe_http`      | Boot a server, wait for port, hit a list of endpoints       | every check passed                    |

## Important config / limits

- **Default timeout: 300s** (configurable per-call or in the constructor). pytest exit code 124 = conventional `timeout` CLI code, used here for command timeouts too.
- **Stream tail-truncation**: `ExecutionResult.as_dict()` keeps the **last 4 KB** of stdout/stderr. Older output is dropped, which is fine for diagnostics but means you can't replay a full pytest log.
- **Server boot polling: 300ms.** `probe_http` checks the port at 300ms intervals; expect up to 300ms of latency between "ready" and "first check sent".
- **`probe_http` only uses `httpx`.** No `requests` fallback.
- **Process group teardown on POSIX.** `preexec_fn=os.setsid` puts the server in its own process group so `_terminate` can SIGTERM the whole tree at once.

## Design decisions

- **Why subprocess + captured output, not in-process execution?** We need to verify behavior in the *real* environment — pytest, build, server boot. In-process execution would inherit agent state and break isolation.
- **Why treat timeout as exit_code=124?** Matches `coreutils timeout` so callers have a single sentinel across tools.
- **Why "0 passed, 0 failed" = failure in `run_pytest`?** A pytest run that didn't actually run tests usually means the test path was wrong. Failing the verdict on that case catches misconfiguration loudly.
- **Why graceful-then-forced terminate?** A SIGKILL of a server with open long-poll requests can leave ports held; SIGTERM-then-wait gives in-flight requests a chance to drain.

## Usage examples

```python
from sin_code_oracle.execution import ExecutionOracle

oracle = ExecutionOracle(root=".")

# Build / test
r = oracle.run_command("pytest -q")
print(r.exit_code, r.duration_s)

# pytest with parsed counts
r = oracle.run_pytest("tests/test_user.py")
print(r.metrics)  # {"passed": 12, "failed": 0, "errors": 0, "skipped": 1}

# HTTP probe
r = oracle.probe_http(
    server_command="uvicorn myapp:app",
    checks=[
        {"path": "/health", "expect_status": 200},
        {"path": "/", "expect_contains": "Welcome"},
    ],
    port=8000,
    boot_timeout=15,
)
print(r.metrics["checks"])
```

## Caveats / footguns

- **Shell injection.** `run_command` uses `shell=True`. Do not pass user-supplied strings to it. If you must run untrusted input, validate it first or switch to `subprocess.run([...], shell=False)`.
- **pytest exit code 5** (no tests collected) is **not** treated as a failure here — that decision lives in `verifiers/tests.py`, not in this module. `run_pytest` uses exit code 0 + 0 failed as its success signal.
- **The HTTP server keeps running until `_terminate`.** If `_wait_for_port` returns False (port didn't open), we still call `_terminate` — so a server that crashed early will not leak.
- **`preexec_fn=os.setsid` is POSIX-only.** On Windows the code path falls back to `proc.terminate()` without a process group, which is best-effort.
