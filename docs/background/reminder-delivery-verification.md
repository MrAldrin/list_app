# Reminder delivery: verification and review record

Delivery started 2026-11-03. This is execution evidence, not current behavior.
The [approved plan](../../plans/due-date-reminders.md) owns the product contract;
its stage records own Conductor status and closeout. The owner selected A/A/A
and authorized implementation, not acceptance/deployment or real pushes.

## Baseline before stage integration

- Aggregate workspace: `/home/hsa/projects/tmp-reminder-delivery`,
  `tmp-reminder-delivery`, parent `zpzpvuyl` / `9abc4e72`.
- Baseline source was unchanged; `.env` was symlinked and isolated dependencies
  installed with `uv sync` and `npm ci`. No database copied from production or
  the coordination workspace. Node 24.15.0, Python 3.13.11.
- Python: Ruff format check, Ruff lint and ty passed. `uv run pytest -q`:
  **1535 passed, 9 skipped**. A missing-build warning occurred because this
  baseline run began in parallel with the first frontend build; tests passed.
- Frontend: Prettier/ESLint, Svelte/TypeScript checks, **1079 Vitest tests** and
  production build passed.
- Browser: `uv run pytest browser_tests -q -n 4`: **399 passed** in 506.96s,
  Chromium/Firefox/WebKit. These are local HTTP browsers, not proof of actual
  Safari/iPhone/Android system push delivery.
- Approval/master/backlog/five-stage brief local Markdown links and anchors
  checked. Aggregate tracked state remained clean after checks.

## S1 reviewed integration — 2026-11-04

- Reviewed UI `swtpolmk` / `d90bc864`, browser-storage fixture `xtwzoknt` /
  `5092264e`, dialog repair `tyyvxrul` / `ab12f9c0`. Fresh Terra/medium review
  approved the complete repair diff; original UI had independent review.
  Matched native WebKit tests reproduced ephemeral cache loss versus isolated
  persistent-profile retention. This supports a test-harness repair, not a
  production cache-eviction claim.
- Final single post-review browser gate on the exact tip: **456 passed**,
  exit 0, 605.22 seconds. No skips, xfails, weakened assertions or repeated
  runs until green. Earlier failures and invalid diagnostic wrappers are not
  passes; their limits remain in the [S1 closeout](../../plans/batches/reminders-s1.md).
- Lead integrated the exact tip into isolated aggregate `mytytmnv` / `fedd46f5`.
  No other feature combined yet; bookmarks stayed fixed. Lead reran Ruff
  format-check/lint, ty and pytest: **1544 passed**, exit 0. Frontend lint/check,
  **1088 unit tests** and production build passed; Svelte check had zero
  errors/warnings. Aggregate tracked state stayed clean. The browser gate was
  not repeated in the identical-source aggregate; final combined verification
  remains later work.
- Durable review and full browser logs/report remain in S1 Pi session artifacts:
  `d67aeaee.../s1-independent-repair-review.md` and
  `b061919f.../s1-final-browser-gate.md`, with retained pytest artifacts.
  UI and baseline child workspaces were safely removed after integration and
  evidence preservation. S1 entry/session retained for dependencies.
- S1 is complete for isolated delivery and S2 UI is unblocked. Full scheduling,
  phone push and final combined verification remain incomplete. No feature
  acceptance, deployment or actual-device delivery is implied.

## Isolated S2 image smoke — 2026-11-04

S2 Conductor executed this on foundation `zystrxzr` / `2e0f70a4`, before
independent acceptance or integration. It does not verify the final combined
app. The trusted Dockerfile was unchanged; rootless Podman built its locked
production dependency path, including runtime `tzdata` 2026.6.

- Image: `localhost/listr-s2-foundation:zystrxzr`,
  `sha256:18e87471956cd4da6a4a8d2671b7bf46e414d02ee22f07b58d05e92e3fdd4cb2`.
- The completed smoke container had no network, mounts, ports, host credentials,
  app startup or database. It was removed with `--rm`; the local image remains.
- Empty `PYTHONTZPATH` and asserted empty `zoneinfo.TZPATH` forced the Python
  package fallback. Oslo gap/fold, canonical shared UTC, date-only null and
  positive/negative-offset IANA zones passed. Later combined-image verification
  remains required; child Python checks and independent review are separate.

Executed commands (the smoke command's formatting below is equivalent):

```shell
podman build --pull=never --tag localhost/listr-s2-foundation:zystrxzr --file /home/hsa/projects/tmp-reminders-s2-foundation/Dockerfile /home/hsa/projects/tmp-reminders-s2-foundation
podman run --rm --network=none --read-only --env PYTHONTZPATH= --env PYTHONPATH=/app/src --entrypoint python localhost/listr-s2-foundation:zystrxzr -c '
import importlib.metadata, zoneinfo
from datetime import UTC, date, datetime, time
from reminders.zoned_time import load_zone, resolve_wall_time
from reminders.due_schedule import DueSchedule
assert zoneinfo.TZPATH == ()
assert resolve_wall_time(date(2026,3,29), time(2,30), load_zone("Europe/Oslo")) == datetime(2026,3,29,1,0,tzinfo=UTC)
assert resolve_wall_time(date(2026,10,25), time(2,30), load_zone("Europe/Oslo")) == datetime(2026,10,25,0,30,tzinfo=UTC)
assert DueSchedule("2026-11-10", "09:00", "Europe/Oslo").due_at() == "2026-11-10T08:00:00.000Z"
assert DueSchedule("2026-11-10").due_at() is None
assert load_zone("Pacific/Apia")
assert load_zone("America/New_York")
assert load_zone("Asia/Kathmandu")
print("IMAGE SMOKE PASS: tzdata=" + importlib.metadata.version("tzdata"))
'
```

## Existing frontend tooling audit

On 2026-11-04, S5's read-only preflight reproduced `npm audit --json`: 19 affected package
entries (4 low, 13 moderate, 2 high), not 19 separate advisories. No frontend
package/lock changed. Installed/locked versions, explicit imports, build paths
and the advisories' current GitHub API affected/patched ranges were inspected.

| High package | Evidence and patch | Reachability found |
| --- | --- | --- |
| `happy-dom` 20.14.5 | [ESM-alias host execution](https://github.com/advisories/GHSA-834v-8h66-3h79), affected 17.0.0–21.0.3, patched 21.0.4; [untrusted-HTML SSRF](https://github.com/advisories/GHSA-c8p4-j97h-3vg8), affected through 20.14.6, patched 21.0.0. Both require at least 21.0.4, outside current major. | Two unit-test files select it, using trusted source/meta-tag fixtures. No reminder-data path into untrusted HTML/module evaluation was identified. Dev/test-host risk is real. |
| `vite` 8.3.2 | [Windows launch-editor command injection](https://github.com/advisories/GHSA-587h-7wmj-h5pm), affected 8.3.0–8.3.2, patched 8.3.3 within current major. Lower-severity advisories also exist. | Current host/image are Linux; no Windows editor-endpoint execution found. This is tooling, not the shipped static reminder code. |

The final Python image copies only the built frontend, not Node or
`node_modules`. The devDependency label alone does not prove safety—Svelte
client code does ship—but these specific tool/import paths show no identified
production browser/server reachability. This was not an exhaustive bundle or
all-platform audit; future tests and Windows collaborators remain unknown.

Keep builds/tests source-trusted. Do not feed attacker-controlled HTML/module
fixtures into Happy DOM; use real browsers/Python for malicious push payload
cases. Use the built-static Python helper for any later owner preview, not an
exposed Vite server.
No automatic audit fix, package upgrade or new reminder release gate is implied.
Separate reviewed tooling maintenance is recommended; its backlog placement
awaits the owner's decision in the [delivery coordination list](../../plans/due-date-reminders.md#delivery-coordination).

## Combined implementation checks

Pending reviewed stage results. Child checks will be preserved in their batch
closeouts, and Lead will run relevant checks on the combined aggregate state.

## Owner review and release limits

- Owner review of the completed implementation is pending.
- `main` and parked `groups` are not delivery targets. No production deploy,
  Railway setting/budget change, real subscription registration or external
  push-provider send has been authorized for this implementation run.
- Phone push provisioning and user opt-in are rollout work. Deterministic
  sender/worker tests cannot establish genuine lock-screen delivery.
