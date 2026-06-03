# `style.py` — Style Verifier

What this file does: runs `ruff check` and `ruff format --check` against a code snippet or path and returns a `Verdict` with one Issue per finding.

## Dependency map

- Imports: `verdict.py`, `runner.py`, stdlib (`tempfile`, `os`, `json`, `pathlib`).
- External tool: `ruff` (install with `pip install ruff`).
- Imported by: `oracle.py` (called from `verify()` and `verify_file()`).

## Public API

| Function                              | Purpose                                              |
|---------------------------------------|------------------------------------------------------|
| `verify_style(code=None, path=None)`  | Run ruff lint + format check, return a Verdict       |

## How it works

1. **Lint pass:** `ruff check --output-format json <target>`. Parses the JSON array; each entry becomes an Issue.
2. **Format pass:** `ruff format --check --diff <target>`. Exit code != 0 ⇒ unformatted file ⇒ one low-severity Issue.

## Severity mapping

| Ruff code prefix | Severity |
|------------------|----------|
| `E*`             | medium   |
| anything else    | low      |

`E` codes (pycodestyle errors like E501 line-too-long) are typically real style bugs; `W` codes are softer warnings.

## Important config / limits

- **Default timeout: 60s per subprocess.** Sufficient for individual files; large repos may need a higher timeout.
- **Missing ruff = WARN Verdict** with an info-level Issue. The verifier degrades gracefully.
- **JSON parse failure = empty findings.** We treat malformed output as "no findings", not as a crash.
- **Format pass exits non-zero** when changes are needed; we don't parse the diff text — just record the file as unformatted.
- **Tempfile cleanup is conditional** on `code is not None`. Caller-supplied `path=` files are left alone.

## Design decisions

- **Why Ruff and not flake8 + black + isort?** Ruff is one tool that does all three, ~100× faster, and shares a config. Less moving parts.
- **Why surface format issues as one Issue instead of parsing the diff?** Diff parsing is brittle and version-dependent. The actionable signal is "this file isn't formatted", not "here's exactly which lines to change" — the user can run `ruff format` to get the latter.
- **Why only `E*` codes are `medium`?** That's the convention the upstream pycodestyle docs use: `E` = errors, `W` = warnings, `C` = conventions. Aligning severity with that hierarchy makes the auto-derived Verdict status meaningful.

## Usage example

```python
from sin_code_oracle.verifiers.style import verify_style

v = verify_style(code="import os\nimport sys\ndef foo():pass\n")
for issue in v.issues:
    print(issue.severity, issue.code, issue.message)
# medium E302 expected 2 blank lines
# low  E704 statement ends with semicolon (... or similar)
```

## Caveats / footguns

- **Ruff config (pyproject.toml `[tool.ruff]`) is honored.** If the user's project disables certain rules, the verifier won't surface them. This is usually desired, but can surprise you on cross-repo checks.
- **The format check doesn't tell you the format diff.** Run `ruff format --diff <file>` yourself if you need it.
- **`--no-cache` is NOT passed.** Ruff's cache is per-project. If you want a clean run, delete `.ruff_cache/`.
