# Test speed decision

## Decision

- Run pytest with **8 workers** by default and unchanged production-cost bcrypt.
- Use `-n 0` for serial debugging; smaller machines can use fewer workers.
- Do not use cheaper or hybrid hashing by default: they are faster but reduce
  confidence that tests match production password-hashing cost.

## Evidence

The recorded benchmark reduced the suite from about 31 seconds to about 6
seconds with 8 workers and unchanged hashing. All 192 tests passed, and the
representative coverage runs matched. Sixteen workers added little benefit.

## Commands

```bash
uv run pytest -q       # default parallel run
uv run pytest -q -n 2  # smaller machine
uv run pytest -q -n 0  # serial/debugging
```

The full experiment details remain in version-control history. Revisit this
record if test performance or hashing fidelity requirements change.
