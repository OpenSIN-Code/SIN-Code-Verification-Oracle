# SIN-Code-Verification-Oracle

Automated verification for Python code — security, performance, correctness, style, and test execution.

## Install

```bash
pip install sin-code-oracle
# or from source
pip install -e ".[dev]"
```

## Quick Start

```python
from sin_code_oracle import VerificationOracle

oracle = VerificationOracle(workspace="/path/to/repo")
verdict = oracle.verify(code="def foo(): return 42", language="python")
print(verdict.to_json())
```

## Verifiers

| Verifier | Tool | What it checks |
|----------|------|---------------|
| Security | bandit | Hardcoded secrets, unsafe eval, SQL injection |
| Performance | AST heuristics | Nested loops, large allocations, missing memoization |
| Correctness | hypothesis | Property-based smoke tests, compile check |
| Style | ruff | Lint, import order, formatting |
| Tests | pytest | Isolated test execution with timeout |

## API

```python
oracle.verify(code="...", language="python")
oracle.verify_file("src/app.py")
oracle.verify_directory("src/")
```

## License

MIT
