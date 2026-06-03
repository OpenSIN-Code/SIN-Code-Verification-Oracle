# `verifiers/__init__.py` — Verifiers Package

What this file does: re-exports the five `verify_*` functions (security, performance, correctness, style, tests) so callers can do `from sin_code_oracle.verifiers import verify_security`.

## Dependency map

- Imports: `verifiers.security`, `verifiers.performance`, `verifiers.correctness`, `verifiers.style`, `verifiers.tests`
- Imported by: `oracle.py` (which calls all five in `verify()`)

## Public API

| Function             | Module          | Purpose                                       |
|----------------------|-----------------|-----------------------------------------------|
| `verify_security`    | `security.py`   | Run bandit, return Verdict                    |
| `verify_performance` | `performance.py`| AST heuristics for perf anti-patterns         |
| `verify_correctness` | `correctness.py`| Hypothesis property-based smoke tests         |
| `verify_style`       | `style.py`      | Ruff lint + format check                      |
| `verify_tests`       | `tests.py`      | Run pytest, parse failure count               |

All five follow the same signature contract: `verify_*(code=None, path=None) -> Verdict`.

## Caveats / footguns

- All verifiers are independent — they don't share state, caches, or temp dirs. Running them in parallel is safe.
- Each verifier can degrade to WARN if its external tool (bandit, ruff, pytest, hypothesis) is missing. A complete oracle run with no tools installed will produce 5 WARN Verdicts merged into 1 WARN.
