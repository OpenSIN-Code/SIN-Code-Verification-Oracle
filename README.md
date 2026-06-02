# SIN-Code Verification Oracle

> Automated verification for Python code — security, performance, correctness, style, and test execution. Independent ground-truth for AI-generated code.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

Part of the [SIN-Code](https://github.com/OpenSIN-Code) agent-engineering stack. Install all subsystems together via the [SIN-Code Bundle](https://github.com/OpenSIN-Code/SIN-Code-Bundle).

## Features

- **Security** — hardcoded secrets, unsafe eval, SQL injection (via bandit)
- **Performance** — nested loops, large allocations, missing memoization (AST heuristics)
- **Correctness** — property-based smoke tests, compile check (via hypothesis)
- **Style** — lint, import order, formatting (via ruff)
- **Tests** — isolated test execution with timeout (via pytest)
- **Diagnostics** — run compilers, type-checkers, and linters as independent oracles
- **Trace diffing** — capture behavior fingerprints before and after edits
- **Eval harness** — run eval suites with a NO-OP baseline for agent benchmarking
- **MCP server** — expose verification tools to AI agents via the Model Context Protocol

## Installation

```bash
pip install -e .
```

Optional MCP server support:
```bash
pip install -e ".[mcp]"
```

See [INSTALL.md](./INSTALL.md) for detailed setup instructions.

## Usage

### Library

```python
from sin_code_oracle import VerificationOracle

oracle = VerificationOracle(workspace="/path/to/repo")

# Verify a code snippet
verdict = oracle.verify(code="def foo(): return 42", language="python")
print(verdict.to_json())

# Verify a single file
verdict = oracle.verify_file("src/app.py")

# Verify a directory
verdicts = oracle.verify_directory("src/")
```

### CLI

```bash
# Run diagnostics (compilers, type-checkers, linters)
oracle diagnostics

# Full verification
oracle verify --root . --test pytest

# Trace capture and diff
oracle trace_capture "pytest tests/" --out trace.json
oracle trace_diff "pytest tests/" --before trace.json

# Eval suite
oracle eval suite.json --label baseline

# Run MCP server
oracle serve
```

## Testing

```bash
pytest tests/ -v
```

## MCP Server

Run the MCP server for agent integration:

```bash
# With the CLI
oracle serve

# Or directly
python -m sin_code_oracle.mcp_server
```

Tools exposed:
- `verify_code(code, language="python")` — verify code correctness using formal proofs and property-based tests
- `generate_properties(code, language="python")` — generate property-based tests for given code

## Integration

The Oracle is designed to work as part of the SIN-Code ecosystem:

- **SIN-Code Bundle** — orchestrates all subsystems from a single CLI (`sin`)
- **Intent-Based Diffing (IBD)** — trigger re-verification for high-risk changes
- **Proof of Correctness (POC)** — feed symbolic and property-based proofs into verdicts
- **Orchestration** — run verification as a gate in CI/agent workflows

## License

MIT — see [LICENSE](./LICENSE).
