"""Performance verification — AST heuristics for common anti-patterns.

We don't run a profiler here; instead we scan the AST for three patterns
that almost always indicate a perf bug:
  1. Nested loops (O(n²) or worse)
  2. Large literal allocations (`[...] * 1_000_000` and friends)
  3. Recursive functions without memoization

Heuristics, not ground truth — false positives are possible and expected.

Docs: performance.doc.md
"""
import ast
import re
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus


# ── Heuristics ─────────────────────────────────────────────────────────
def _has_nested_loop(node: ast.AST) -> bool:
    """True if `node` contains any For/While with another For/While inside it.

    Walks the subtree twice: first for outer loops, then for inner loops
    under each outer. We explicitly compare identities (`is not outer`) so
    a single-statement loop is not flagged as self-nested.
    """
    for outer in ast.walk(node):
        if isinstance(outer, (ast.For, ast.While)):
            for inner in ast.walk(outer):
                if inner is not outer and isinstance(inner, (ast.For, ast.While)):
                    return True
    return False


def _detect_large_allocations(source: str) -> list[Issue]:
    """Flag `[...]*100000`-style repeated list allocations.

    The 5-digit threshold (`\\d{5,}`) is conservative — it's unlikely to
    fire on a legitimate 100-element default. False positives are possible
    for code that intentionally builds huge test fixtures; tune the
    threshold if that becomes a problem.
    """
    issues = []
    pattern = re.compile(r"\[\s*.*\s*\]\s*\*\s*(\d{5,})")
    for i, line in enumerate(source.splitlines(), 1):
        match = pattern.search(line)
        if match:
            issues.append(
                Issue(
                    verifier="performance",
                    severity="medium",
                    message=f"Large repeated list allocation detected ({match.group(1)} items)",
                    line=i,
                    code=line.strip(),
                )
            )
    return issues


class _RecursiveCallFinder(ast.NodeVisitor):
    """Tiny NodeVisitor that records whether a function calls itself by name."""

    def __init__(self, name: str):
        self.name = name
        self.found = False

    def visit_Call(self, node: ast.Call):
        # Only direct self-calls (a.foo() does not count as recursion).
        if isinstance(node.func, ast.Name) and node.func.id == self.name:
            self.found = True
        # generic_visit keeps us descending into nested expressions.
        self.generic_visit(node)


def _detect_missing_memoization(source: str) -> list[Issue]:
    """Heuristic: recursive function without `lru_cache` or explicit `memo`/`cache`.

    Returns an Issue per such function. False positives: functions that
    recurse on a strictly-decreasing argument and don't need memoization.
    The severity is `low` precisely because of this — it's a hint, not a bug.
    """
    issues = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
            # ast.dump produces a stable string representation; checking
            # for "lru_cache" / "memo" / "cache" in it is a quick proxy for
            # "does the body mention memoization". False positives are possible
            # (e.g. a `cache = {}` local variable) but rare in practice.
            body_str = ast.dump(node, annotate_fields=False)
            finder = _RecursiveCallFinder(name)
            for stmt in node.body:
                finder.visit(stmt)
            calls_self = finder.found
            has_lru = "lru_cache" in body_str
            has_memo = "memo" in body_str or "cache" in body_str
            if calls_self and not (has_lru or has_memo):
                issues.append(
                    Issue(
                        verifier="performance",
                        severity="low",
                        message=f"Recursive function '{name}' may benefit from memoization",
                        line=node.lineno,
                        code=ast.get_source_segment(source, node),
                    )
                )
    return issues


# ── Verifier ───────────────────────────────────────────────────────────
def verify_performance(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Scan code or path for nested loops, large allocations, and missing memoization.

    Returns a Verdict. An `ERROR` verdict is returned for missing input or
    unrecoverable I/O failure; a `SyntaxError` in the source is also an ERROR
    (we can't AST-walk broken code).
    """
    issues: list[Issue] = []
    source = ""
    if code is not None:
        source = code
    elif path is not None:
        try:
            source = Path(path).read_text()
        except Exception as exc:
            return Verdict(
                status=VerdictStatus.ERROR,
                issues=[],
                summary=f"Could not read {path}: {exc}",
            )
    else:
        return Verdict(status=VerdictStatus.ERROR, issues=[], summary="No target provided")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return Verdict(
            status=VerdictStatus.ERROR,
            issues=[],
            summary="Syntax error in source; performance check skipped",
        )

    # Walk the AST and check each loop for nesting. The duplicate
    # `_has_nested_loop` walk inside the outer walk is O(n²) but `n` here
    # is the number of top-level statements, so it stays cheap.
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            if _has_nested_loop(node):
                issues.append(
                    Issue(
                        verifier="performance",
                        severity="medium",
                        message="Nested loop detected — potential O(n²) complexity",
                        line=node.lineno,
                        code=ast.get_source_segment(source, node),
                    )
                )

    issues.extend(_detect_large_allocations(source))
    issues.extend(_detect_missing_memoization(source))

    summary = f"Performance scan found {len(issues)} issue(s)"
    return Verdict.from_issues(issues, summary)
