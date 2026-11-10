# Task 5 closeout

## Research decision and review

- Recommend proposed **A: an opt-in foreground daily brief**. It adds one
  proactive daily offer and private durable handling state, not another due
  panel. It does not alert while the app is closed.
- Research only. No S3 implementation, settings activation, recovery,
  migration, external delivery, deployment or scope approval occurred.
- Fresh independent combined report/source review: **PASS**, no material
  blockers. Exact reviewed source: `yzsnswqlwxqpyrsoyxtmkxzltquxvryr` /
  `961bb2f086bafe68e5ae2c67dbd472fcb0fa95ad`.
  [Full review](final-independent-review.md); effective Luna/xhigh confirmed
  by host events in [model receipts](child-model-receipts.json).
- The reviewer asked only that a later B brief include cancellation,
  restart/restore, stale-cycle and duplicate-suppression tests if B is chosen,
  and that actual composition/cleanup evidence be appended separately. B is
  not approved; the main report's proposed behavior was not changed.
- [Scout disposition](scout-disposition.md) preserves the raw analyses while
  rejecting optional restore safety, broad P2 exposure and per-tab receipts.

## Separate actual-entry composition verification

Lead requested this after the archive analysis. Report/source review had
priority and ran while the parent performed these checks. These are fresh
checks of the combined overnight entry, **not S3 tests or approval**. Task1
remains red; no full browser matrix was rerun and no browser failure was fixed.

Actual root: `/home/hsa/projects/list_app-night-s3-review`; entry parent:
`762c384b9aa5e4acd4ee90012ae6df22eb92b98a`. The accepted behavior comparison
stays `9e34df13e5b773ebf88032047fbe26a1088877bb`.

[Exact runner](run-composition-checks.sh), [all exits](composition/exits.tsv),
and per-command logs under `composition/` preserve commands, cwd, time zone,
timestamps, output and first results. No failed command was repaired/retried.

| Check | Exact command after runner environment | Result |
| --- | --- | --- |
| Python roots | `uv run --offline --no-sync python -` with retained assertions | 0; app/helper imports, pytest root/config/testpaths resolve this entry |
| Python dependency consistency | `uv pip check --python /home/hsa/projects/list_app/.venv/bin/python` | 0 |
| Node roots | `node --input-type=module -` with retained assertions | 0; current frontend package/config and copied vendor modules |
| Node dependency consistency | `npm ls --depth=0` | 0 |
| Frontend lint | `npm run lint` | 0 |
| Frontend types | `npm run check` | 0; no errors or warnings |
| Frontend build | `npm run build` | 0; built this entry, not another workspace |
| Full unit suite, UTC | `TZ=UTC npm test` | 0; 54 files, 1,115 tests, 7.88 s |
| Full unit suite, Oslo | `TZ=Europe/Oslo npm test` | 0; 54 files, 1,115 tests, 7.69 s |
| Python format check | `uv run --offline --no-sync ruff format --check .` | 0; 274 files already formatted |
| Python lint | `uv run --offline --no-sync ruff check .` | 0 |
| Python types | `uv run --offline --no-sync ty check` | 0; configured `src/` scope |
| Full configured Python suite | `uv run --offline --no-sync pytest -q --basetemp docs/background/reminders-s3-scope-review-evidence/composition-temp` | 0; 1,792 passed, no skips, 56.58 s; configured `-n 8` |

The last command's actual absolute temporary path is retained in its log.
The frontend was built before pytest, so frontend-route checks were not
skipped for a missing build. All 13 commands returned zero on their first run.
These counts remain separate from the historical snapshot's 150 tests.

### Environment and source proof

- `env -i` kept HOME, PATH and LANG; runner set explicit synthetic credentials,
  `DB_PATH=:memory:`, dotenv disabled, push/reminders off and no reload. Lead's
  pre-dispatch `.env` symlink (`../list_app/.env`) was present. The runner did
  not create, copy or explicitly read it; it used `env -i` and
  `PYTHON_DOTENV_DISABLED=1`. Frontend checks used their own `frontend/` root
  with no `envDir` override. No runtime file-access trace was retained. Tests can override only their fixtures.
- Existing shared Python environment was reused without sync/install. Its
  project/lock bytes match this entry. Python application and helper module
  origins, pytest config/root/testpaths and Python paths are in
  `composition/python-roots.log`. Shared site-packages supply dependencies,
  not another workspace's app source.
- Copied the existing 145 MiB node_modules from `list_app-night-docs`, without
  installation or dependency edits. Its package.json and package-lock.json
  bytes match this entry. Node v24.15.0, local config and module origins are
  in `composition/node-roots.log`. Lint/type/build/Vitest logs name this root.
- [Before hashes and reuse identity](composition-source-before.json) and
  [after hashes](composition-source-after.json): **all 372 source/test/config
  files unchanged**, P2 settings flag still false. No test weakening, source
  repair, dependency/config change, formatting write or product edit.
- Tests used memory or owned temporary SQLite/files. The existing shutdown
  test starts/stops its own disposable app subprocess using synthetic data
  and a free local port. There was no persistent app server or provider/
  external request. Existing docs/gallery servers and port8080 were untouched.
- Checks ran serially in visible floating no-focus pane87/tab24. Available
  disk was checked against 6 GiB before each command. The runner does not
  retain each free-space value; it refuses work below the floor. Completion
  still had about13 GiB free. No heavy checks overlapped each other.

## Documentation/source-link checks and honest failures

- Canonical docs wrapper: exit0, 51 warnings, the same warning count as Task4;
  54 fragment-free redirects and 2,824 generated local links validated.
  [Runner](run-docs-check.sh), [log](docs-build.log),
  [summary and exclusion](docs-build-summary.json). These warnings were not
  repaired or hidden. All later Task5 changes remain in excluded background
  content, so they do not alter the site inputs or output.
- The background report is **not** site-rendered. Separate
  [source-link check](run-report-link-check.sh) renders authored Markdown only
  to memory with Python Markdown tables/fenced_code/toc. It checks local
  targets/fragments, report table/heading parsing, and records un-fetched
  external links. Raw scouts and inherited historical evidence are not
  rewritten or given current render approval.
- First source-check attempt returned1: the new diagnostic incorrectly
  rejected the valid `inherited-reviews/` directory link. The unchanged
  [initial result](report-source-link-check-initial.json) is retained. Only
  this new diagnostic was corrected to accept existing trailing-slash source
  directories without fragments. No app, test, config or link target changed.
  [Final result](report-source-link-check.json) records actual final checks.
- Other setup failures are retained in [research checks](research-checks.md).
  They are not application-check failures. The combined-entry commands had
  no first failures, installation blockers or retries.

## Preservation and cleanup

[Protection after](protection-after.json), [runner](run-preservation-check.sh),
[log](preservation-check.log), and exit0 prove:

- All **5,525 archived files /730,350,862 bytes** match the before SHA-256
  manifest; file set unchanged.
- All **36 exact resume refs** still resolve; all **60 exact source-tree
  fingerprints** match. Conflicts and divergent alternatives are preserved.
- All bookmarks and all other workspace revisions are unchanged. Accepted
  baseline, prior nightly results, entry merge and parked S3 were not moved.
- No push, GC, rebase, integration movement or app migration occurred.

[Cleanup](cleanup.json): historical snapshot forgotten/removed after its
clean-source check; passed temporary data removed only after logs were saved.
Owned finished panes79,85,87,88 were closed. Copied node_modules and generated
frontend verification output were removed; shared dependency sources remain.
All bounded children are complete. No owned server/job/snapshot remains.
The Lead-owned entry workspace and interactive Conductor remain for handoff.
The generated excluded docs site is local-only; no preview server was started.

Only this report and its evidence directory changed. The frozen proposed
behavior body is identical to the independently reviewed version; final
check/review/cleanup facts are additive. A final packet check can name the
exact closeout source without claiming the reviewer ran those tests.

Graph control stays with the Conductor until it sends exact final result IDs
and a clean empty working-copy child to Lead, then explicitly quiesces. The
Lead owns any result bookmark, acceptance and entry-workspace cleanup.
