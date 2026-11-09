# Proposed test tiers and cadence — 9 November 2026

Proposal for `integration` `6d4b0dcb`, not a change to today's gates. The
owner's deploy decision is pytest, frontend checks, change-based selection or
tier commands, and the three-engine smoke set. The full three-engine suite
must **not** block deploy. Until the follow-up changes the guides and workflow,
continue to follow the current requirements. A failed required check is not a
pass. This proposal does not authorize skips, retries or deployment.

Inputs: inventory `lr-005.1.1` (`psqyoumn`) and selection map `lr-005.1.2`
(`mprklvpl`), both awaiting acceptance on separate bookmarks. Their files are
`docs/background/test-inventory-2026-11-09.md` and
`docs/background/test-selection-map-2026-11-09.md`; they are not on this base.
The map's full-suite trigger is a conservative proposal, not a deploy gate:
run that full suite nightly or earlier for feedback, without blocking deploy.

## Proposed tiers

Commands below run from the repo root unless noted. `B` means
`flock /home/hsa/.local/state/night-loop/list_app/browser.lock`; prepend it to
every browser or Android test command, and run only one such suite at a time.
Build first when needed. Times are rough planning estimates, not service levels;
selected and smoke times need measurement. Setup and builds are extra.

| When | Command | Expected elapsed | Protects | Misses |
| --- | --- | --- | --- | --- |
| Inner loop, after a local edit | `uv run pytest -q -n 0 <affected-python-paths>`; in `frontend/`, `npm test -- <affected-test-paths>`; for a browser issue, `B uv run pytest -q -n 0 <affected-browser-paths> -k chromium` | Seconds to minutes, unmeasured | Fast feedback on the edited behavior | Other paths, engines and integrations; omit commands for unaffected layers, not failing tests |
| Agent hand-in | Affected Python and frontend paths as above; `B uv run pytest -q -n 4 <affected-browser-paths> -k chromium`; plus applicable formatting, lint, types and build checks | Minutes, unmeasured | Selected cross-layer behavior in one real engine | Firefox, WebKit and unselected paths; no claim of full coverage |
| Before integration, proposed | Run `P`, `F`, selected tests and `S` below on the candidate; for broad/shared changes also schedule `A` below | Python ~54–61 s, frontend tests ~9 s, smoke and other checks unmeasured | Full Python/frontend checks, affected journeys and three-engine critical paths | Full browser coverage is delayed; this proposal needs owner acceptance before it replaces current completion checks |
| Before deploy, owner-set gate | Run `P`, `F`, selected tests and `S` on the deploy revision; for relevant install, persisted-login or network-recovery changes also run `D` | As above; Android unmeasured | Critical three-engine paths plus change-specific risks and relevant Android behavior | Other browser journeys, real Safari/phones and production HTTPS; full browser run does not block deploy |
| Nightly, proposed; also earlier for broad/shared changes | Run `P`, `F` and `A`; run `D` when relevant and emulator is ready | Full browser baseline ~11 min plus other checks; Android unmeasured | Broad regression feedback across all three engines | Findings can arrive after integration or deploy; investigate and fix forward, not silently ignore |

**Commands:**

- `P`: `uv run ruff format --check . && uv run ruff check . && uv run ty check && uv run pytest -q`. Build the frontend first so build-dependent Python tests run; report any skips.
- `F`: `cd frontend && npm run lint && npm run check && npm test && npm run build` (run in a subshell if continuing from the root). This includes Prettier's check via lint; it does not rewrite files.
- `S`: `B uv run pytest browser_tests -q -n 4 -k 'test_add_restore_check_quantity_edit_and_undo or test_visitor_views_and_edits_by_link_and_reset_stops_it or test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes or test_bell_counts_overdue_and_today_and_groups_the_panel'`. Confirm collection includes each body in Chromium, Firefox and WebKit; zero matches or missing engines fail the gate.
- `A`: `B uv run pytest browser_tests -q -n 4`. Preserve and report existing skips and failures.
- `D`: `B env ANDROID_HOME="$HOME/Android/Sdk" uv run python -m pytest android_tests -q -n 0`; use the prepared, unlocked emulator in the [Android guide](../android-emulator-testing.md). Missing emulator is not a pass.

Selection is manual until a selector is implemented and verified. Use the
selection map to union affected paths and explain the selection. Unknown paths,
shared sync/auth/schema/service-worker code, configuration and changed test
fixtures trigger a full run for feedback. For the deploy gate, still run the
relevant affected paths plus smoke; the full three-engine run remains non-blocking.
Do not treat unknown coverage as an empty selection. Docs-only changes use
appropriate document checks; preview changes also select its build test.

The `lr-gt2.1` per-body engine matrix is an **option**, not an assumed change:
the owner approved its design with timed-due retained on all three engines until
`lr-gt2.4` is fixed; worker-count sampling and implementation are separate.
It does not replace the smoke gate or prove a runtime saving. The commands above
assume the current suite, not that matrix.

## Follow-up and evidence

`lr-005.1.8` must update `AGENTS.md` completion checks,
`docs/browser-testing.md` tier commands and lock guidance, and the deployment
checklist in `docs/deployment.md`; reconcile the deploy script's actual checks
without implying it runs smoke or selection today. Set explicit ownership for
nightly runs and failure follow-up; this task implements no scheduler or
selector. Preserve the deploy backup and approval gates.

[Saved runtime evidence](../reports/test-suite-runtime-2026-11-05.md) reports
662.37 s for a full browser baseline with two failures and 120 intentional
skips, not a clean pass. Inventory attempt 1 reports Python 53.84 s with nine
build-dependent skips and UTC frontend 1,112 passed / two failed. Android and
smoke are unmeasured. These results do not verify this candidate. No tests were
run for this documentation proposal; no product or test code was changed.
