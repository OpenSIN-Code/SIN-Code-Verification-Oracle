# `oracle.py` — Main Verification Oracle

What this file does: defines `VerificationOracle`, the public orchestrator that fans out to the five verifiers (security, performance, correctness, style, tests) and merges their results into a single `Verdict`.

## Dependency map

- Imports: `verdict.py` (data models), `report.py` (`merge_verdicts`), `verifiers/__init__.py` (all five `verify_*` functions)
- Imported by: `__init__.py` (re-exported as the package's public symbol), `cli.py`, `mcp_server.py`, examples, and any external user code

## Public API

| Symbol                                   | Purpose                                                |
|------------------------------------------|--------------------------------------------------------|
| `VerificationOracle(workspace=".")`      | Construct with a workspace root                        |
| `.verify(code=None, language="python", test_command=None, run_diagnostics=True)` | Run all verifiers, return merged `Verdict` |
| `.verify_file(path)`                     | Run 4 verifiers (no test) on a single file             |
| `.verify_directory(path)`                | Run `.verify_file` on every `*.py` under `path` (recursive) |

## Important config / limits

- **Only Python is fully supported.** Other languages return a `WARN` verdict with the message `"Language '<lang>' not fully supported; limited checks applied"`.
- **Tempfile lives inside `workspace`.** When you pass `code=...`, we write it to a `.py` temp file in `workspace` and clean it up in a `finally` block. This matters for tools that resolve paths relative to CWD.
- **`run_diagnostics=False`** strips the `diagnostics` dict from the merged verdict to keep the response small.
- **`verify_directory` runs files sequentially** — no cross-file analysis, no parallelism. Big repos will be slow.

## Design decisions

- **Why OR-fold the verdicts in `merge_verdicts`?** A security failure shouldn't mask a performance regression (or vice versa). Reporting the worst case and the union of issues gives the most diagnostic value.
- **Why a single `verify()` with `code` / `path` parameters?** Three call sites (CLI, MCP, eval harness) all want the same fan-out; one method is simpler than three.
- **Why does `verify_file` skip tests?** A single file usually has no runnable tests. Call `.verify(...)` with a `test_command` instead.
- **Why not parallelize `verify_directory`?** Subprocess verifiers (bandit, ruff) already have their own internal parallelism. Adding another layer of concurrency can OOM the host.

## Usage example

```python
from sin_code_oracle import VerificationOracle

# 1. Verify a code snippet
oracle = VerificationOracle(".")
v = oracle.verify(code='password = "secret123"\n', language="python")
print(v.to_json())

# 2. Verify a whole repo
v = oracle.verify(test_command="pytest -q", run_diagnostics=True)
print(v.status)  # PASS | WARN | FAIL | ERROR

# 3. Per-file batch
for fv in oracle.verify_directory("src/"):
    print(fv.summary)
```

## Caveats / footguns

- **Bandit and ruff must be installed** for security/style verifiers. If they're missing, the verifier returns a `WARN` Verdict with an info-level issue — not a hard fail.
- **`verify_directory` does not follow symlinks safely** — `Path.rglob` will recurse into linked directories and may produce duplicate Verdicts.
- **Tempfile is created with `delete=False`**, then unlinked in a `finally`. If the process is SIGKILLed between write and unlink, you'll find a stray `tmp*.py` in the workspace. This is intentional (Windows can't unlink open files).
