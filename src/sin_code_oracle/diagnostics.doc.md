# `diagnostics.py` — Diagnostics Oracle

What this file does: runs every installed language tool (pyright, ruff, tsc) against a project and normalizes the output into a single `DiagnosticsReport`. Extending to a new language is a one-class change.

## Dependency map

- Imports: stdlib only (`json`, `shutil`, `subprocess`, `dataclasses`, `pathlib`)
- Imported by: `cli.py` (the `diagnostics` subcommand), `mcp_server.py` (the `run_diagnostics` tool)
- No I/O outside the project being scanned.

## Public API

| Symbol              | Purpose                                                        |
|---------------------|----------------------------------------------------------------|
| `Diagnostic`        | Normalized finding (file, line, col, severity, message, code)  |
| `DiagnosticsReport` | Aggregated report: `available_tools`, `missing_tools`, `diagnostics`, `error_count`, `warning_count` |
| `DiagnosticProvider`| Abstract base class. Subclass to add a new language tool.     |
| `PyrightProvider`   | `pyright --outputjson` — strongest static Python signal        |
| `RuffProvider`      | `ruff check --output-format=json` — fast lint                 |
| `TscProvider`       | `tsc --noEmit --pretty false` — TypeScript                    |
| `DiagnosticsOracle` | Orchestrator. `check(root, changed_files=None)` returns a report. |

## Important config / limits

- **Default subprocess timeout: 120s.** Pyright on a cold cache can be slow.
- **Graceful degradation.** A missing tool is recorded in `missing_tools` and the oracle proceeds with the rest. The oracle never fails just because one provider is absent.
- **Line numbers are exposed 1-based** for pyright (pyright returns 0-based internally).
- **`changed_files=None` walks the entire tree.** For big repos, callers should pass an explicit list to keep latency predictable.

## Design decisions

- **Why delegate to real tools instead of re-implementing analysis?** Reinventing AST-based linting gives a strictly weaker signal than pyright/ruff. The cost is subprocess overhead, but the upside is using battle-tested, community-maintained analyzers.
- **Why normalize severity to 3 values (error/warning/info)?** Different tools use different vocabularies. A single vocabulary lets `error_count` / `warning_count` be computed uniformly and lets consumers treat all tools the same.
- **Why catch `TimeoutExpired` / `OSError` per provider?** A single flaky tool (e.g. tsc on a broken `tsconfig.json`) must not break the whole diagnostics pass.

## Usage example

```python
from sin_code_oracle.diagnostics import DiagnosticsOracle

report = DiagnosticsOracle().check("/path/to/project")
print(report.error_count, report.warning_count)
for d in report.diagnostics:
    print(d.file, d.line, d.severity, d.message)
```

## Adding a new language

```python
class EslintProvider(DiagnosticProvider):
    name = "eslint"
    tool = "eslint"
    extensions = (".js", ".ts", ".tsx")

    def run(self, root, files):
        # parse `eslint --format json` and yield Diagnostic(...) instances
        ...

oracle = DiagnosticsOracle(providers=[EslintProvider(), PyrightProvider()])
```

## Caveats / footguns

- **`changed_files` filtering is by file extension only.** A provider whose `extensions` is `((".py",))` will run if *any* `.py` file is in the list — it does not cross-check that the changed file is the one being scanned.
- **JSON parse failures are silent.** A provider emitting garbage stdout yields zero findings, not a crash. Inspect the provider's stderr separately if a tool seems to miss findings.
