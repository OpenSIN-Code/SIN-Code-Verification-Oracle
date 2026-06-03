# `eval_harness.py` — SWE-bench-style Evaluation Harness

What this file does: runs an evaluation suite (a list of tasks with hidden verification) against an agent and produces a `resolved_rate` you can track over time and across configuration changes.

## Dependency map

- Imports: `execution.ExecutionOracle`
- Imported by: `cli.py` (`oracle eval` subcommand)
- Writes nothing to disk permanently — every task uses a fresh `tempfile.mkdtemp` and is cleaned in a `finally` block.

## Public API

| Symbol         | Purpose                                                                |
|----------------|------------------------------------------------------------------------|
| `EvalTask`     | One task: seed workspace, verify commands, optional setup              |
| `TaskOutcome`  | Result of one task: resolved?, duration, per-cmd verify results        |
| `EvalReport`   | Aggregate: `resolved / total` + `resolved_rate` (0..1)                 |
| `EvalHarness`  | Orchestrator. `load_suite(path)` → list[EvalTask]; `run_suite(tasks, agent)` → EvalReport |

`AgentFn` is a type alias: `Callable[[str, EvalTask], None]`. The agent edits files in the given workspace path; its return value is ignored.

## Important config / limits

- **Default per-task timeout: 600s.** Override via `task.timeout_s` for slow installs.
- **Tasks run sequentially.** Parallelism is the caller's responsibility.
- **The agent NEVER sees `verify_commands`.** This is the SWE-bench trust model: the only ground truth is what the hidden verify commands report.
- **Suite JSON format**: either `{"tasks": [...]}` or a top-level array of task objects. Required task fields: `id`, `workspace`, `verify_commands`. Optional: `setup_command`, `description`, `timeout_s`, `metadata`.
- **`resolved_rate` is rounded to 4 decimals** in the property. For a percentage, multiply by 100 in the consumer.

## Design decisions

- **Why hidden verify commands?** If the agent saw the verify spec, it would game it. The same trust boundary is what makes SWE-bench scores meaningful.
- **Why `tempfile.mkdtemp` per task?** Two reasons: (1) re-runs are hermetic, (2) multiple tasks in one suite can share a Python process without filesystem collisions.
- **Why catch all exceptions in the agent step?** A buggy agent that throws should count as "not resolved", not crash the harness. That way, a single broken task doesn't sink the whole benchmark run.

## Usage example

```python
from sin_code_oracle.eval_harness import EvalHarness

def my_agent(workspace, task):
    # edit files in `workspace` to attempt the task
    ...

harness = EvalHarness(config_label="my-agent-v1")
tasks = harness.load_suite("evals/swe_bench_mini.json")
report = harness.run_suite(tasks, my_agent)
print(f"{report.resolved}/{report.total} = {report.resolved_rate:.1%}")
```

Suite JSON:

```json
{
  "tasks": [
    {
      "id": "fix-add-bug",
      "workspace": "examples/workspaces/fix-add-bug",
      "verify_commands": ["python -m pytest -q tests/test_add.py"]
    }
  ]
}
```

## Caveats / footguns

- **The agent's edits persist only inside the temp dir.** Don't expect the seed `workspace/` to be modified — the harness copies, not references.
- **Agent exceptions are recorded, not raised.** Check `outcome.error` in the report; an empty `error` field means the agent returned cleanly even if it didn't solve the task.
- **No concurrency.** If you have 1000 tasks, this will be slow. Wrap `harness.run_suite` in a `ProcessPoolExecutor` at the task level if needed.
