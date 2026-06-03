# `__init__.py` — Public Package API

What this file does: re-exports the public symbols of `sin_code_oracle` so that `from sin_code_oracle import VerificationOracle` works. Also pins the package version.

## Dependency map

- Imports: `.oracle` (VerificationOracle), `.verdict` (Verdict, VerdictStatus, Issue)
- Imported by: external user code, the CLI, the MCP server

## Public API

```python
from sin_code_oracle import VerificationOracle, Verdict, VerdictStatus, Issue
```

`__version__` is `"0.1.0"`.

## Caveats / footguns

- Adding a new top-level class? Update `__all__` here or `import *` callers won't see it.
