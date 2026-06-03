# `security.py` — Security Verifier

What this file does: runs Bandit (Python security linter) against a code snippet or a path, parses the JSON output, and returns a `Verdict` with each finding as an `Issue`.

## Dependency map

- Imports: `verdict.py` (data models), `runner.py` (subprocess wrapper)
- External tool: `bandit` (install with `pip install bandit`)
- Imported by: `oracle.py` (called from `verify()` and `verify_file()`)

## Public API

| Function                                    | Purpose                                                  |
|---------------------------------------------|----------------------------------------------------------|
| `verify_security(code=None, path=None)`     | Run bandit, return a Verdict with per-finding Issues     |

## Important config / limits

- **Bandit thresholds: `-ll -ii`** — only medium/high severity AND medium/high confidence. Low-confidence or low-severity findings are filtered out by Bandit itself, not by us. This keeps the signal-to-noise ratio high.
- **Default timeout: 60s.** Sufficient for most snippets; large files may need more.
- **Missing bandit = WARN Verdict**, not FAIL. The verifier degrades gracefully so a missing tool doesn't sink the whole oracle.
- **JSON parse failure = empty results** (not a crash). If bandit emits garbage, we record 0 issues.

## Design decisions

- **Why shell out to `bandit` instead of using its Python API?** The CLI's JSON output is stable and well-documented; the Python API churns between releases. The CLI is the public contract.
- **Why a tempfile for code snippets?** Bandit needs a file path to scan. Writing the snippet to a tempfile in the system temp dir is the cleanest way to feed it.
- **Why lowercase the severity?** `VerdictStatus` and the auto-derivation in `Verdict.from_issues` expect lowercase. Bandit returns uppercase, so we normalize.

## Usage example

```python
from sin_code_oracle.verifiers.security import verify_security

v = verify_security(code='password = "secret123"\n')
for issue in v.issues:
    print(issue.severity, issue.message, "rule", issue.details.get("test_id"))
```

## Caveats / footguns

- **Bandit is line-based, not semantic.** It catches `subprocess.Popen(shell=True)` but not a taint that flows through 5 function calls. Use it as one signal, not the whole story.
- **Tempfile cleanup is conditional on `code is not None`.** If the caller passes a `path=...`, we don't touch it — it's their file.
- **The `details` dict on each Issue is free-form.** Today it only has `test_id`, but future fields (e.g. `cwe`, `more_info`) are likely. Consumers should `.get(...)` defensively.
