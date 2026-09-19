# Test speed experiments

## Scope

Compare opt-in strategies before choosing another permanent change. The existing
session-scoped Home password hash stays in place. No production code, test
assertions, default pytest configuration, or project dependencies were changed
during the experiments. Subsequently, 8 workers with unchanged hashing were
approved: `pytest-xdist` is now a dev dependency and pytest defaults to `-n 8`.
Use `-n 0` for serial runs or override the count for smaller machines.

## Method

- Local machine reports 16 logical CPUs; results depend on available CPU resources.
- Each timing is wall-clock time for the entire command, including startup.
- Two full runs per variant, executed sequentially, not competing benchmarks.
  The first eight variants were repeated in reverse order to reduce order bias.
- All runs passed all 192 tests. No tests were skipped or assertions removed.
- Timings exclude coverage instrumentation. Separate coverage runs checked quality.
- `pytest-xdist` 3.8.0 was provided temporarily through `uv run --with pytest-xdist`.
- Every worker has its own in-memory SQLite database; filesystem tests use `tmp_path`.
- Existing Starlette TestClient deprecation warnings remain.

## Results

Savings are relative to the current cached-fixture baseline, not the original
69.7-second suite. Means are descriptive, not statistically precise estimates.

| Strategy | Run 1 | Run 2 | Mean | Time saved | Test-quality trade-off |
| --- | ---: | ---: | ---: | ---: | --- |
| Current baseline | 31.29s | 31.22s | 31.26s | — | None; reference |
| 2 parallel workers | 16.86s | 16.76s | 16.81s | 46% | No intentional loss; real hashing and assertions unchanged |
| 4 parallel workers | 9.44s | 9.45s | 9.45s | 70% | Same as above |
| 8 parallel workers | 6.10s | 6.05s | 6.07s | 81% | Same as above; exact measured coverage matches baseline |
| 16 parallel workers | 5.45s | 5.39s | 5.42s | 83% | Same tests; more CPU/process overhead for only 0.65s extra gain |
| Cheaper hashing | 8.42s | 8.39s | 8.41s | 73% | Real bcrypt, but most test calls no longer exercise production-default cost |
| Hybrid hashing | 21.93s | 21.92s | 21.93s | 30% | Password-hash and database-setup modules keep normal cost; other modules do not |
| Cheaper hashing + 4 workers | 3.98s | 3.97s | 3.97s | 87% | Same cheaper-hashing compromise |
| Hybrid hashing + 4 workers | 7.24s | 7.26s | 7.25s | 77% | Same hybrid compromise |
| Cheaper hashing + 8 workers | 3.19s | 3.18s | 3.18s | 90% | Same cheaper-hashing compromise |
| Hybrid hashing + 8 workers | 5.45s | 5.45s | 5.45s | 83% | Same hybrid compromise; saves only 0.62s over normal hashing + 8 workers |

### What “cheaper hashing” means

A temporary pytest plugin changes bcrypt's default salt cost from 12 to 4 only
while test bodies execute. It still generates random salts and uses real bcrypt
hashing and password verification. Explicit cost arguments are preserved.
Fixtures, collection-time initialization, subprocess startup, and production
source code remain unchanged. In particular, checks against the normal-cost Home
fixture still pay the normal verification cost.

Hybrid mode exempts all test bodies in `test_password_hashes.py` and
`test_database_setup.py`. Other authentication/invitation tests use reduced cost,
so hybrid is not equivalent to retaining full production fidelity everywhere.

Neither strategy fakes successful authentication. However, identical assertion
counts or coverage do not prove identical test quality: changing cost settings
reduces fidelity to deployment and may conceal cost-dependent problems. A
permanent implementation should retain explicit production-cost checks and a
normal-cost full-suite execution path.

### Coverage comparison

Separate `pytest-cov` runs used `--cov=src --cov-branch` for baseline, 8 workers,
cheaper hashing, and hybrid hashing. All four produced **identical per-file sets
of executed/missing lines and branches**, not just identical percentages:

- 912 / 1,857 statements covered (49.1%).
- 141 / 440 branches covered (32.0%).

These are measurements of the current suite under this instrumentation, not a
claim of comprehensive application coverage. Subprocess-only behavior was not
separately instrumented. Combined hashing/parallel modes and 16 workers passed
all tests but were not separately coverage-instrumented.

Parallelism changes scheduling and process boundaries. It can expose or hide
cross-test state dependencies; matching coverage cannot rule that out. Keep the
serial command available. It does not make individual tests into concurrency
stress tests.

## Recommendation

Start with **8 workers and unchanged hashing**: about 6 seconds, no intentional
reduction in what is tested or in password-hashing fidelity. Use fewer workers on
smaller machines. Sixteen workers offer little extra benefit here.

Do not adopt hybrid hashing for now: it introduces fidelity trade-offs for only
about 0.6 seconds saved over 8 workers. Cheaper hashing plus 8 workers reaches
about 3.2 seconds, but choose that only if saving another 2.9 seconds matters
enough to justify a fast mode plus a separate normal-cost run.

## Reproduction

Baseline and parallel execution need no repository changes:

```bash
uv run --with pytest-xdist pytest -q -n 0
uv run --with pytest-xdist pytest -q -n 8
```

For hashing trials, save the following as `speed_experiment.py` in a temporary
directory outside the repository:

```python
import os

import bcrypt
import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    mode = os.environ.get("LIST_APP_BENCH_MODE", "normal")
    preserve = item.path.name in {"test_password_hashes.py", "test_database_setup.py"}
    if mode == "normal" or (mode == "hybrid" and preserve):
        return (yield)
    original = bcrypt.gensalt

    def cheaper_salt(rounds=4, prefix=b"2b"):
        return original(rounds=rounds, prefix=prefix)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(bcrypt, "gensalt", cheaper_salt)
        return (yield)
```

From the repository root, substitute that directory for `/tmp/experiment`:

```bash
PYTHONPATH=/tmp/experiment LIST_APP_BENCH_MODE=cheap \
  uv run --with pytest-xdist pytest -q -p speed_experiment -n 0

PYTHONPATH=/tmp/experiment LIST_APP_BENCH_MODE=hybrid \
  uv run --with pytest-xdist pytest -q -p speed_experiment -n 8
```

Use `normal` mode for the reference with the same plugin loaded (as used in the
benchmark). Repeat each command with shell `time`. The original trials used
Python's `time.perf_counter()` around each subprocess. Coverage can be reproduced
by adding `--with pytest-cov` before `pytest` and
`--cov=src --cov-branch --cov-report=json:/tmp/coverage.json` after it.

## Progress

- [x] Inspect isolation and hashing behavior.
- [x] Benchmark baseline and ten alternatives twice each.
- [x] Verify all 192 tests pass in every experiment.
- [x] Compare exact line/branch coverage for four representative modes.
- [x] Record reproducible experiments and quality trade-offs.
- [x] User chooses 8 parallel workers with unchanged hashing.
- [x] Add the dev dependency and default configuration; document serial overrides.
