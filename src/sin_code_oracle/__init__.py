"""SIN-Code-Verification-Oracle — automated verification for code quality.

Re-exports the public API: `VerificationOracle`, `Verdict`, `VerdictStatus`,
`Issue`. See the module docstrings of `oracle.py` and `verdict.py` for
detailed usage.

Docs: __init__.doc.md
"""

from .oracle import VerificationOracle
from .verdict import Verdict, VerdictStatus, Issue

__all__ = ["VerificationOracle", "Verdict", "VerdictStatus", "Issue"]
__version__ = "0.1.0"
