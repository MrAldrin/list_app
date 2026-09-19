# List app

## Tests

```bash
uv run pytest -q
```

Tests run across 8 worker processes by default. Each worker has its own test
database; production password-hashing settings remain unchanged.

Override the worker count on smaller machines, or run serially for debugging:

```bash
uv run pytest -q -n 2  # Two workers
uv run pytest -q -n 0  # Serial (also use this with --pdb)
```

Benchmark results and trade-offs: [test speed experiments](plans/test-speed-experiments.md).
