# `trace_diff.py` — Behavioral Trace-Diff

What this file does: captures the observable behavior of a shell command (stdout, exit code, emitted files, structured events) as a "behavior trace", and computes a structured delta between two traces. The killer use case is catching behavioral regressions that pass tests but change real-world output.

## Dependency map

- Imports: stdlib only (`hashlib`, `json`, `re`, `subprocess`, `dataclasses`, `pathlib`).
- Imported by: `cli.py` (`trace-capture` and `trace-diff` subcommands).

## Public API

| Symbol            | Purpose                                                                  |
|-------------------|--------------------------------------------------------------------------|
| `BehaviorTrace`   | Snapshot: command, exit_code, normalized stdout, events, artifact hashes, `fingerprint` |
| `TraceDelta`      | Structured diff: per-dimension change flags + human-readable `summary`   |
| `TraceDiffer`     | Orchestrator. `capture(command, events_file?, timeout=120)` → `BehaviorTrace`; `diff(before, after)` → `TraceDelta` |

## Important config / limits

- **Default timeout: 120s.** Override per call.
- **Fingerprint: 16 hex chars of SHA-256.** Collisions are astronomically rare; not a security property — just a fast equality check.
- **Noise patterns** (timestamps, UUIDs, hex addresses, `/tmp/...` paths, `\d+\.\d+s` durations) are replaced with stable tokens before diffing. The list is conservative by design — adding more patterns is risky (false negatives on semantic changes).
- **Event file format: JSON-Lines.** One JSON object per line. Lines that don't parse go in as `{"raw": "<normalized>"}` so they're still diffed.
- **Artifact hashing: 16-char SHA-256 content digest.** Full file content is read; very large artifacts can be slow.

## Design decisions

- **Why normalize noisy tokens before fingerprinting?** Without normalization, a `Date.now()` in the output would make every trace unique. The `_NOISE_PATTERNS` list turns them into stable placeholders so semantically equivalent runs produce the same fingerprint.
- **Why a 4-dimension diff (exit / stdout / artifacts / events)?** A behavioral change can show up in any one of them. Reporting all four lets consumers triage: a stdout change is usually cosmetic, an exit change is usually a regression.
- **Why OR-fold `changed`?** A trace is "changed" if *any* dimension changed. The detailed flags let consumers still see which one.
- **Why `fingerprint` as a 16-char hash, not 64?** A trace is meant to be human-glanceable in CI output. 16 chars is enough for collision-free equality checks at this scale.

## Usage example

```python
from sin_code_oracle.trace_diff import TraceDiffer

differ = TraceDiffer(root=".", artifact_globs=["dist/**/*.js"])
before = differ.capture("python -m myapp.cli hello", events_file="events.jsonl")
# ... agent edits files ...
after = differ.capture("python -m myapp.cli hello", events_file="events.jsonl")
delta = differ.diff(before, after)
if delta.changed:
    print(delta.summary)
```

## Caveats / footguns

- **The trace ignores stderr.** If your command's behavior is in stderr (e.g. a logging-only tool), capture it via `events_file` instead, or wrap the command: `command 2>&1 | tee out.log`.
- **Artifact globs use `pathlib.Path.glob`, not `rglob`.** Use `**/*` inside the pattern if you need recursion.
- **Timeout exit code 124** matches `ExecutionOracle` for consistency.
- **The `events_file` is read AFTER the command exits.** If the command crashes mid-write, you may see a partial event log.
