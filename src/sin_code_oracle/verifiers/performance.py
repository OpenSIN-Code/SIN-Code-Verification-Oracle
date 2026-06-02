# Purpose: Performance verification: detect O(n²) loops, large allocations, missing memoization.
# Docs: performance.doc.md
import ast
import re
from pathlib import Path
from typing import Any

from ..verdict import Issue, Verdict, VerdictStatus


def _has_nested_loop(node: ast.AST) -> bool:
    """Check if an AST node contains a nested loop."""
    for outer in ast.walk(node):
        if isinstance(outer, (ast.For, ast.While)):
            for inner in ast.walk(outer):
                if inner is not outer and isinstance(inner, (ast.For, ast.While)):
                    return True
    return False


def _detect_large_allocations(source: str) -> list[Issue]:
    """Detect large literal list/dict/set allocations."""
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
    def __init__(self, name: str):
        self.name = name
        self.found = False

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == self.name:
            self.found = True
        self.generic_visit(node)


def _detect_missing_memoization(source: str) -> list[Issue]:
    """Heuristic: recursive function without functools.lru_cache or explicit memo."""
    issues = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
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


def verify_performance(code: str | None = None, path: str | Path | None = None) -> Verdict:
    """Scan code for common performance anti-patterns."""
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
