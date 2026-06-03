"""Command-line interface for the SIN-Code Verification Oracle.

Exposes Typer subcommands that let humans and CI pipelines drive the oracle
end-to-end: run diagnostics, produce a Verdict, capture and diff behavior
traces, run an evaluation suite, and launch the MCP server.

Docs: cli.doc.md
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from .diagnostics import DiagnosticsOracle
from .eval_harness import EvalHarness
from .oracle import VerificationOracle
from .trace_diff import TraceDiffer

app = typer.Typer(help="SIN-Code Verification Oracle — independent ground-truth verification for AI agents.")
console = Console()


# ── Diagnostics ────────────────────────────────────────────────────────
@app.command()
def diagnostics(root: str = typer.Argument(".")):
    """Run every installed language tool (pyright, ruff, tsc) against `root`."""
    report = DiagnosticsOracle().check(root)
    console.print_json(json.dumps(report.as_dict()))


# ── Verify ─────────────────────────────────────────────────────────────
@app.command()
def verify(
    root: str = typer.Option(".", "--root"),
    test: str = typer.Option(None, "--test", help="Test command, or literal 'pytest'"),
    build: str = typer.Option(None, "--build", help="Build command"),
    no_diagnostics: bool = typer.Option(False, "--no-diagnostics"),
):
    """Produce a Verdict from ground-truth signals (ignores agent self-report).

    Exits 0 on PASS, 1 on FAIL — CI and agent loops can gate on it directly.
    """
    oracle = VerificationOracle(root=root)
    verdict = oracle.verify(
        test_command=test,
        build_command=build,
        run_diagnostics=not no_diagnostics,
    )
    # Color encodes three-state: green=PASS, yellow=UNVERIFIED, red=FAIL
    # Keeps the panel readable when Verdict is intentionally inconclusive.
    color = "green" if verdict.passed else ("yellow" if not verdict.verified else "red")
    status = "PASS" if verdict.passed else ("UNVERIFIED" if not verdict.verified else "FAIL")
    console.print(Panel(
        f"[bold {color}]{status}[/bold {color}]  confidence={verdict.confidence.value}",
        title="Verification Oracle",
    ))
    for r in verdict.reasons:
        console.print(f"  • {r}")
    # Non-zero exit on FAIL so CI / agent loops can gate on it.
    raise typer.Exit(code=0 if verdict.passed else 1)


# ── Trace capture / diff ───────────────────────────────────────────────
@app.command()
def trace_capture(
    command: str,
    out: str = typer.Option("trace.json", "--out"),
    root: str = typer.Option(".", "--root"),
    events_file: str = typer.Option(None, "--events"),
):
    """Capture a behavior trace and write it to --out (run before an edit)."""
    trace = TraceDiffer(root=root).capture(command, events_file=events_file)
    Path(out).write_text(json.dumps(trace.as_dict(), indent=2))
    console.print(f"[green]captured[/green] fingerprint={trace.fingerprint} -> {out}")


@app.command()
def trace_diff(
    command: str,
    before: str = typer.Option(..., "--before", help="Path to a previously captured trace.json"),
    root: str = typer.Option(".", "--root"),
    events_file: str = typer.Option(None, "--events"),
):
    """Capture now and diff against a previously captured trace (exit 1 on change)."""
    differ = TraceDiffer(root=root)
    before_data = json.loads(Path(before).read_text())
    after = differ.capture(command, events_file=events_file)
    changed = before_data.get("fingerprint") != after.fingerprint
    console.print_json(json.dumps({
        "changed": changed,
        "before_fingerprint": before_data.get("fingerprint"),
        "after_fingerprint": after.fingerprint,
    }))
    # Exit 1 if behavior changed so CI can gate on behavioral regression.
    raise typer.Exit(code=1 if changed else 0)


# ── Eval suite ─────────────────────────────────────────────────────────
@app.command()
def eval(
    suite: str = typer.Argument(..., help="Path to a suite JSON file"),
    label: str = typer.Option("default", "--label"),
):
    """Run an eval suite with a NO-OP agent (baseline). Wire your agent in code."""
    harness = EvalHarness(config_label=label)
    tasks = harness.load_suite(suite)

    def noop_agent(workspace: str, task) -> None:
        # Replace this with a call into your real agent. The baseline measures
        # how many tasks are already resolved before any agent action.
        return None

    report = harness.run_suite(tasks, noop_agent)
    console.print(Panel(
        f"resolved {report.resolved}/{report.total}  ([bold]{report.resolved_rate:.1%}[/bold])",
        title=f"Eval: {label}",
    ))
    console.print_json(json.dumps(report.as_dict()))


# ── MCP server ─────────────────────────────────────────────────────────
@app.command()
def serve():
    """Run as an MCP server for agent integration (stdio transport)."""
    from .mcp_server import main
    main()


if __name__ == "__main__":
    app()
