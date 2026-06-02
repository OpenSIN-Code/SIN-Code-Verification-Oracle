# `report.py` — Verdict Merger

What this file does: merges multiple verifier verdicts into a single consolidated verdict.

## Dependencies

- Imported by: `oracle.py`, tests

## Public API

- `merge_verdicts(verdicts)` → Verdict

## Notes

The merged status is the worst of all inputs: `ERROR` > `FAIL` > `WARN` > `PASS`.
