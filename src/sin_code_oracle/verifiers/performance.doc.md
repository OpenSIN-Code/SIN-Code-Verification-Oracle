# `performance.py` — Performance Verifier

What this file does: detects nested loops, large allocations, and missing memoization via AST heuristics.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `verify_performance(code=None, path=None)` → Verdict

## Notes

Heuristic-based: flags `O(n^2)` patterns, list comprehensions over large ranges, and recursive functions without caching.
