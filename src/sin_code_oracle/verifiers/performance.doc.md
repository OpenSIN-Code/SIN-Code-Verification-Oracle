# `performance.py` — Performance Verifier

What this file does: scans Python source for three AST patterns that almost always indicate a performance bug: nested loops, large literal allocations, and recursive functions without memoization. Heuristics only — false positives are possible.

## Dependency map

- Imports: stdlib only (`ast`, `re`, `pathlib`).
- Imported by: `oracle.py` (called from `verify()` and `verify_file()`).

## Public API

| Function                                    | Purpose                                                      |
|---------------------------------------------|--------------------------------------------------------------|
| `verify_performance(code=None, path=None)`  | Run the three heuristics, return a Verdict                  |

## Heuristics

1. **Nested loops.** A `for`/`while` containing another `for`/`while`. Severity: `medium`. False positive risk: low — a nested loop is almost always wrong.
2. **Large literal allocations.** Regex matches `\[...\] * \d{5,}` (5+ digit multiplier). Severity: `medium`. False positive risk: low for `* 100000+`, but a 5-digit test fixture multiplier is possible.
3. **Missing memoization.** A `FunctionDef` that calls itself by name and doesn't contain `lru_cache` / `memo` / `cache` in its body. Severity: `low`. False positive risk: moderate — naive recursion on a strictly-decreasing argument doesn't need memoization.

## Important config / limits

- **5-digit threshold for "large allocation"** is the heuristic. Tune `re.compile(r"\[\s*.*\s*\]\s*\*\s*(\d{5,})")` if your codebase legitimately uses 100k+ element lists.
- **`memo`/`cache` substring match** is a quick proxy for "has memoization". A function with a local `cache = {}` variable will be (correctly) skipped. A function whose body says "use memoization" in a comment will be (incorrectly) skipped too. False negatives are possible.
- **No profiling.** The verifier doesn't actually measure runtime. It only flags patterns that *look* like perf bugs.
- **Syntax errors return ERROR verdict** with summary `"Syntax error in source; performance check skipped"`. The AST walker can't run on broken code.

## Design decisions

- **Why AST + regex, not a real profiler?** Profiling requires running the code with representative inputs, which is expensive and brittle. AST patterns catch the most common bugs at near-zero cost.
- **Why is "missing memoization" `low` severity?** Recursive functions on strictly-decreasing arguments (e.g. quicksort) don't need memoization. Severity `low` keeps the auto-derivation from inflating to FAIL.
- **Why 5 digits, not 4?** A 4-digit threshold (`* 1000+`) catches too many legitimate uses (e.g. `numpy.zeros(1000)` is fine).
- **Why substring search on `ast.dump` for `lru_cache`?** It's a fast proxy. A precise check would parse the body looking for `@functools.lru_cache` decorators, which is more correct but more code.

## Usage example

```python
from sin_code_oracle.verifiers.performance import verify_performance

v = verify_performance(code="""
def find_pairs(items):
    pairs = []
    for i in items:
        for j in items:           # nested loop!
            pairs.append((i, j))
    return pairs

def fib(n):
    if n < 2: return n
    return fib(n - 1) + fib(n - 2)  # recursion, no memo
""")
for issue in v.issues:
    print(issue.severity, issue.message, "at line", issue.line)
```

## Caveats / footguns

- **False positives on memoization.** A function that recurses on a decreasing counter (e.g. `def countdown(n): return countdown(n - 1) if n else None`) will be flagged. Tune the heuristic if your codebase has many such cases.
- **The large-allocation regex is single-line.** Multi-line `[*range(1000000)]` is not matched.
- **`_RecursiveCallFinder` only matches `ast.Name` calls.** Recursion via attribute (`self.fib(...)`) is not detected — methods on classes are out of scope.
