# `cli.py` — Command-line Interface

What this file does: exposes a Typer CLI that drives the Verification Oracle end-to-end — `diagnostics`, `verify`, `trace-capture` / `trace-diff`, `eval`, and `serve`.

## Dependency map

- Imports from: `diagnostics.py`, `eval_harness.py`, `oracle.py`, `trace_diff.py`
- Imports lazy: `mcp_server.main` (only inside `serve` — keeps the CLI runnable without the optional `mcp` extra)
- Used by: end users via the `oracle` console script (entry point declared in `pyproject.toml`)

## Subcommands

| Command         | Purpose                                                       | Exit code              |
|-----------------|---------------------------------------------------------------|------------------------|
| `diagnostics`   | Run every installed language tool against a directory         | always 0               |
| `verify`        | Produce a Verdict from ground-truth signals                   | 0 PASS / 1 FAIL        |
| `trace-capture` | Snapshot a behavior trace to JSON                             | always 0               |
| `trace-diff`    | Compare a fresh trace against a saved one                     | 0 same / 1 changed     |
| `eval`          | Run an evaluation suite with a baseline (NO-OP) agent         | always 0               |
| `serve`         | Start the MCP server (requires `pip install sin-code-oracle[mcp]`) | follows MCP convention |

## Important config / limits

- `--test` may be a literal command string (e.g. `"pytest -x"`) — Typer splits on whitespace, so quote it in the shell.
- `verify` prints a Rich `Panel` with one of three colors: green = PASS, yellow = UNVERIFIED (insufficient evidence), red = FAIL.
- `trace-diff` exit codes are designed to be used directly as a CI gate: behavioral regression ⇒ non-zero ⇒ build fails.

## Design decisions

- Why Typer + Rich? Typer auto-generates `--help` and shell completions; Rich keeps the multi-state Verdict panel readable.
- Why a NO-OP agent in `eval`? A baseline run with no agent shows how many tasks are resolved "for free" by the seed — useful for measuring how much an agent actually contributes.
- Why lazy-import `mcp_server`? The `mcp` extra is optional; the rest of the CLI must work without it.

## Usage examples

```bash
# Run all diagnostics + verifiers on the current repo
oracle verify --root . --test "pytest -q"

# Capture a behavior trace on the base revision
oracle trace-capture "python -m myapp.cli hello" --out before.json

# After editing, diff — non-zero exit if behavior changed
oracle trace-diff "python -m myapp.cli hello" --before before.json

# Run a baseline eval
oracle eval examples/eval_suite.json --label baseline
```

## Caveats / footguns

- The CLI does NOT mutate the workspace, but verifiers spawn real subprocesses (bandit, ruff, pyright, pytest). A repo without those tools returns WARN-level Verdicts, not failures.
- `trace-capture` writes a 16-char fingerprint, NOT the full trace — the JSON in `--out` is the only place to keep the full payload.
