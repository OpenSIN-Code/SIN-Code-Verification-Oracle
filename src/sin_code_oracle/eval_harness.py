"""Eval Harness (SWE-bench style).

Without measurement, "state of the art" is a belief. This harness lets you
define a suite of tasks with objective pass criteria and run any agent against
them, producing a resolved-rate you can track over time and across config
changes (e.g. "does enabling the SCKG retrieval actually raise the score?").

A task is:
  - a workspace (a directory snapshot to copy),
  - a setup command (install deps),
  - a `solve` callback (your agent edits files in the workspace),
  - a verification spec (commands/pytest that must pass = the hidden test).

The agent NEVER sees the verification commands; resolution is judged purely by
the Execution Oracle. This is the same trust model SWE-bench uses.

Docs: eval_harness.doc.md
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .execution import ExecutionOracle


# ── Data models ────────────────────────────────────────────────────────
@dataclass
class EvalTask:
    """One task in a suite: a workspace to seed, a setup step, and a verification spec."""

    id: str
    workspace: str                      # path to seed directory (copied per run)
    verify_commands: list[str]          # hidden oracle: all must exit 0 to "resolve"
    setup_command: str | None = None    # e.g. "pip install -e ."
    description: str = ""
    # 600s default: most SWE-bench-style tasks finish in <2 min;
    # raise this for slow installs / large test suites.
    timeout_s: int = 600
    metadata: dict = field(default_factory=dict)


@dataclass
class TaskOutcome:
    """Result of running a single EvalTask against an agent."""

    task_id: str
    resolved: bool
    setup_ok: bool
    duration_s: float
    verify_results: list[dict] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict:
        """Return a JSON-serializable view of this outcome."""
        return self.__dict__


@dataclass
class EvalReport:
    """Aggregated result of a full EvalHarness.run_suite() call."""

    total: int
    resolved: int
    outcomes: list[TaskOutcome] = field(default_factory=list)
    config_label: str = "default"
    started_at: str = ""

    @property
    def resolved_rate(self) -> float:
        """Fraction of tasks resolved (4 decimal places). 0.0 if no tasks."""
        return round(self.resolved / self.total, 4) if self.total else 0.0

    def as_dict(self) -> dict:
        """Return a JSON-serializable view of this report."""
        return {
            "config_label": self.config_label,
            "started_at": self.started_at,
            "total": self.total,
            "resolved": self.resolved,
            "resolved_rate": self.resolved_rate,
            "outcomes": [o.as_dict() for o in self.outcomes],
        }


# An agent is any callable that, given a fresh workspace path and the task,
# edits files in place to attempt a solution. Return value is ignored; only
# the resulting filesystem state is verified.
AgentFn = Callable[[str, EvalTask], None]


# ── Harness ────────────────────────────────────────────────────────────
class EvalHarness:
    """Run an evaluation suite against an agent and produce an EvalReport.

    Each task gets its own temp directory (a copy of the seed) so concurrent
    agents in the same suite would not collide. The harness itself is
    sequential — parallelism is the caller's job.
    """

    def __init__(self, config_label: str = "default"):
        # `config_label` is recorded on the report so you can A/B different
        # agent configs and compare resolved rates on the same suite.
        self.config_label = config_label

    def _load_task(self, raw: dict) -> EvalTask:
        """Hydrate an EvalTask from a JSON-decoded dict.

        Required keys: id, workspace, verify_commands.
        Optional: setup_command, description, timeout_s, metadata.
        """
        return EvalTask(
            id=raw["id"],
            workspace=raw["workspace"],
            verify_commands=raw["verify_commands"],
            setup_command=raw.get("setup_command"),
            description=raw.get("description", ""),
            timeout_s=raw.get("timeout_s", 600),
            metadata=raw.get("metadata", {}),
        )

    def load_suite(self, path: str) -> list[EvalTask]:
        """Load a suite from a JSON file.

        Accepts either a top-level array `[task, ...]` or
        an object `{"tasks": [task, ...]}`.
        """
        data = json.loads(Path(path).read_text())
        tasks = data["tasks"] if isinstance(data, dict) else data
        return [self._load_task(t) for t in tasks]

    def run_task(self, task: EvalTask, agent: AgentFn) -> TaskOutcome:
        """Run one task: copy workspace, run setup, invoke agent, run hidden verify."""
        start = time.monotonic()
        # Per-task temp dir: makes re-runs hermetic and lets multiple tasks
        # in the same suite share a process safely.
        tmp = tempfile.mkdtemp(prefix=f"oracle-eval-{task.id}-")
        try:
            # 1. Materialize an isolated copy of the workspace.
            seed = Path(task.workspace)
            if seed.is_dir():
                shutil.copytree(seed, tmp, dirs_exist_ok=True)
            oracle = ExecutionOracle(root=tmp, default_timeout=task.timeout_s)

            # 2. Setup.
            setup_ok = True
            if task.setup_command:
                setup = oracle.run_command(task.setup_command)
                setup_ok = setup.success

            # 3. Let the agent attempt the task (edits files inside tmp).
            try:
                agent(tmp, task)
            except Exception as e:  # an agent crash is a non-resolution, not a harness crash
                return TaskOutcome(
                    task_id=task.id, resolved=False, setup_ok=setup_ok,
                    duration_s=round(time.monotonic() - start, 3),
                    error=f"agent raised {type(e).__name__}: {e}",
                )

            # 4. Hidden verification: every command must pass.
            verify_results = []
            resolved = True
            for cmd in task.verify_commands:
                res = oracle.run_command(cmd)
                verify_results.append({"command": cmd, "success": res.success, "exit_code": res.exit_code})
                # AND-fold: any failing verify command ⇒ task is not resolved.
                resolved = resolved and res.success

            return TaskOutcome(
                task_id=task.id,
                # Both setup AND every verify command must pass for resolution.
                resolved=resolved and setup_ok,
                setup_ok=setup_ok,
                duration_s=round(time.monotonic() - start, 3),
                verify_results=verify_results,
            )
        finally:
            # Always clean up, even on exceptions. `ignore_errors` so a
            # crash during agent execution can't leak temp dirs.
            shutil.rmtree(tmp, ignore_errors=True)

    def run_suite(self, tasks: list[EvalTask], agent: AgentFn) -> EvalReport:
        """Run every task sequentially and aggregate into an EvalReport."""
        report = EvalReport(
            total=len(tasks),
            resolved=0,
            config_label=self.config_label,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        for task in tasks:
            outcome = self.run_task(task, agent)
            report.outcomes.append(outcome)
            if outcome.resolved:
                report.resolved += 1
        return report
