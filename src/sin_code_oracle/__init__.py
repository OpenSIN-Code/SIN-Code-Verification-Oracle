"""SIN-Code-Verification-Oracle — automated verification for code quality.

Docs: README.md
"""

from .oracle import VerificationOracle
from .verdict import Verdict, VerdictStatus, Issue

__all__ = ["VerificationOracle", "Verdict", "VerdictStatus", "Issue"]
__version__ = "0.1.0"
