"""Verifiers package — re-exports the five `verify_*` functions.

Each function in this package takes either `code=` (a source string) or
`path=` (a file/dir path) and returns a `Verdict`. They are completely
independent of each other; `oracle.py` is what orchestrates them.

Docs: __init__.doc.md
"""
from .security import verify_security
from .performance import verify_performance
from .correctness import verify_correctness
from .style import verify_style
from .tests import verify_tests

__all__ = [
    "verify_security",
    "verify_performance",
    "verify_correctness",
    "verify_style",
    "verify_tests",
]
