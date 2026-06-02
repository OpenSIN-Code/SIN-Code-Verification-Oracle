#!/usr/bin/env python3
"""Example: Verify a simple code snippet with the Oracle."""

from sin_code_oracle import VerificationOracle

oracle = VerificationOracle(workspace=".")

# Example 1: Clean code
print("=== Clean Code ===")
clean = "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)\n"
verdict = oracle.verify(code=clean, language="python")
print(verdict.to_json())

# Example 2: Code with issues
print("\n=== Code with Issues ===")
bad = 'password = "secret123"\nfor i in range(1000):\n    for j in range(1000):\n        pass\n'
verdict = oracle.verify(code=bad, language="python")
print(verdict.to_json())

# Example 3: Verify current workspace tests
print("\n=== Workspace Tests ===")
verdict = oracle.verify(test_command="pytest", run_diagnostics=False)
print(verdict.to_json())
