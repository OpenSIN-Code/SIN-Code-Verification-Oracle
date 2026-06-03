# `runner.py` — Subprocess Runner

What this file does: thin convenience wrapper around `subprocess.run` that always returns a dict (never raises) and exposes a `timed_out` flag for easy checking. Plus a helper that runs a Python code snippet from a temp file.

## Dependency map

- Imports: stdlib only (`subprocess`, `sys`, `tempfile`, `os`, `pathlib`).
- Imported by: `verifiers/security.py`, `verifiers/style.py`, `verifiers/tests.py`, `verifiers/correctness.py` — basically every verifier that shells out to a tool.

## Public API

| Function                                    | Purpose                                                              |
|---------------------------------------------|----------------------------------------------------------------------|
| `run_command(cmd, cwd, timeout, env, capture_output)` | Run a command, return dict `{returncode, stdout, stderr, timed_out}` |
| `run_in_temp_file(code, suffix=".py")`      | Write `code` to a temp file and run it with the current Python       |

## Important config / limits

- **Default timeout: 60s.** Override per call. On timeout: `returncode=-1`, `timed_out=True`.
- **`run_command` does NOT use `shell=True`.** You must pass an argv list. This is intentional — shell injection is much harder when the args are split by Python.
- **`run_in_temp_file` uses `sys.executable`** as the interpreter — never `"python"` on PATH, which could be a different version.
- **Tempfiles are unlinked in a `finally` block.** A crash in the subprocess doesn't leak them.
- **`FileNotFoundError` is mapped to `returncode=-1` with a clear stderr** — callers can distinguish "tool not installed" from "tool exited non-zero".

## Design decisions

- **Why a dict instead of a dataclass?** The verifiers consume the result with `result["stdout"]` etc., and `dataclasses` would add boilerplate for little gain. A dict is the most Pythonic contract here.
- **Why `returncode=-1` on timeout?** Matches the conventional "abnormal exit" sentinel. Callers that care about the distinction check `timed_out`.
- **Why `sys.executable` in `run_in_temp_file`?** The verifiers might run in a virtualenv with a different Python version. Using the current interpreter guarantees a version match.

## Usage examples

```python
from sin_code_oracle.runner import run_command, run_in_temp_file

# Run a linter
r = run_command(["ruff", "check", "."], timeout=30)
if r["timed_out"]:
    print("ruff took too long")
elif r["returncode"] != 0:
    print(r["stderr"])

# Run a code snippet
r = run_in_temp_file("print('hello world')")
print(r["stdout"])  # "hello world\n"
```

## Caveats / footguns

- **`cmd` is passed directly to `subprocess.run` as argv.** If you need shell features (pipes, redirects), wrap with `["bash", "-c", "..."]` — and never pass untrusted input.
- **`run_in_temp_file` deletes the temp file even on timeout**, which is fine because the subprocess has already exited (subprocess timeout kills the process).
- **The dict's `stdout` / `stderr` are always strings** (text mode). Tools that emit binary output (e.g. `xxd`) will be unreadable.
