# lr-347.10.3 — browser, driver and server cost

> Kept on 2026-11-21 as the record of this answer. The spike scripts (change `yvvwtrny`), the task workspace and the raw traces were deleted. Paths and commands below no longer exist.

- Date: 2026-11-13, 20:03–20:28 CET. Baseline: `integration` = `wnuszwpy 53457053`.
- Spike: `yvvwtrny d73e44f6`, local bookmark `lr-347.10.3`. Nothing accepted or published.
- Workspace: `/home/hsa/projects/list_app-lr-347.10.3`. Evidence paths below are relative to it. The shared evidence directory was not edited, to keep all edits in this workspace.
- Status: measurements retained; **all required Python checks pass** after the owner raised the host inotify limit. Verified on 2026-11-14 at 06:48 CET. No browser measurements were repeated.
- Review: final diff and retained evidence checked by the continuing worker. The current worker settings specify reviewer `none`, so no separate review was run despite the earlier continuation note. This is not an independent review. The spike remains unaccepted and unpublished.

## Answer to the owner — three sentences

TypeScript Playwright showed no speed gain: the three median test-call times were 0.3%, 1.3% and 3.8% slower, with overlapping sample ranges, so this sample does not establish a faster full suite. The same browser and Node-based Playwright engine do most of the shared work; changing the client language does not remove their retry waits. A TypeScript server was not built, so its gain is unknown: the current server has a material cost, but much of the measured sign-in cost is bcrypt, which a language rewrite does not remove.

The TypeScript tests ran against the unchanged Python server. A backend rewrite is not needed to use TypeScript Playwright.

## Runs and exact commands

All heavy checks held both locks, in this order:

```text
flock /home/hsa/.local/state/night-loop/browser.lock \
  flock /home/hsa/.local/state/night-loop/list_app/browser.lock <command>
```

Evidence directory `E=.night-evidence/lr-347/lr-347.10.3` contains the commands, outputs and traces. `run-full.sh` and `run-compare.sh` retain the complete environment and lock setup.

| Run | Command after locks | Exit | Result / process wall time |
| --- | --- | --- | --- |
| Full Chromium | `env PYTHONPATH="$PWD/browser_tests:$PWD/tests" BA3_PHASE_LOG="$PWD/$E/full-phases.jsonl" uv run pytest browser_tests -p ba3_probe -q -n 6 --tier-engine chromium --durations=0 --durations-min=0 --basetemp "$PWD/$E/full-pytest" --junitxml "$PWD/$E/full.xml"` | 0 | 162 passed, existing 40 skipped; pytest 65.64 s, process 66.34 s |
| Server timer, tags file | Same environment, `BA3_REQUEST_TIMING=1`, `pytest browser_tests/test_svelte_tags.py -p ba3_probe -q -n 0 --tier-engine chromium --durations=0 --durations-min=0`, with `tags-*` output paths | 0 | 7 passed; process 11.21 s |
| Added CPU counters, tags file | Same serial tags command, separate `cpu-tags-*` output paths | 0 | 7 passed; process 9.67 s |
| Paired comparison | `uv run python browser_tests/ba3_compare.py /tmp/list-app-ba3-ts-PXs52e "$PWD/$E/comparison"` | 0 | 30 successful invocations; about 136 s total; each `run.json` records exact arguments, exit and wall time |

Trace recording, DOM snapshots, sources and screenshots stayed on. No product code, existing test body, assertion, skip or timeout changed. The full run has 19.929 setup, **285.481 call** and 57.214 teardown worker seconds. This is not the older 270-call-second sample.

## Part A — measured cost

These costs overlap. A browser API call can wait for the server, and multiple processes can use CPU at once. **They must not be added as independent slices of total runtime.**

| Cost / measurement | Seconds | % of full-suite call time | Meaning |
| --- | ---: | ---: | --- |
| Browser + common Node engine, traced API interval union | 225.973 | 79.2% | Browser work, app waits, Node work and retries; not browser-only CPU |
| Outside traced API intervals | 59.507 | 20.8% | Upper bound for client/harness gaps; also contains untraced context and API setup |
| App server CPU | 67.350 | 23.6% | CPU snapshots for 144 of 162 calls; others had no standard server or stopped/restarted it; not a wall-time saving |
| Retry-wait overshoot model | about 22.490; range 0–44.980 | about 7.9%; range 0–15.8% | Model, not direct readiness measurement or a confidence interval |
| Fixed-delay API calls during test call | 13.191 elapsed; 13.100 requested | 4.6% | Includes conditional helper polling; not all removable |

**The trace residual is not Python driver time.** In the seven-test tags file, call time was 6.436 s and traced API time was 4.130 s. The 2.306 s difference includes 1.876 s of server-to-headers time outside trace intervals. Only 0.430 s remains outside both trace and server-header intervals.

For a repeatable, non-overlapping *occupancy* allocation of that file, give server-header intervals priority, then traced APIs, then gaps:

| Component, tags file | Seconds | % of its 6.436 s call time |
| --- | ---: | ---: |
| Server request pending to response headers, interval union | 3.085 | 47.9% |
| Browser + shared Node engine, outside those server intervals | 2.921 | 45.4% |
| Driver / harness / untraced gaps, outside both | 0.430 | 6.7% |

This is an allocation rule, **not a causal browser/driver/server profile**. Browser work can run during a server interval. Some server body work occurs after headers. Summed header durations were 3.482 s before removing concurrent requests; finite request lifetimes summed to 4.106 s. SSE connection lifetimes were excluded. Server CPU was 2.400 s (37.3% of call seconds). Eight sign-ins used 1.709 header-seconds, about 26.6% of call time.

The separate CPU-counter run had 5.802 call seconds: Python client 0.383 CPU s, Node driver 1.470 CPU s, browser descendants at least 5.600 CPU s, server 2.380 CPU s. These values exceed elapsed time when added because processes run concurrently. Browser CPU is a lower bound: processes that exit before a snapshot are not counted. `/proc` counters have 10 ms resolution. The repeated tags runs show host/cache variation; do not extrapolate either file percentage to every test.

### API method timings — full suite, call phase only

| Method | Count | Total seconds | Median ms | P90 ms |
| --- | ---: | ---: | ---: | ---: |
| expect | 1,914 | 113.838 | 4.464 | 113.374 |
| click | 798 | 43.416 | 36.403 | 67.056 |
| fill | 511 | 14.241 | 9.162 | 111.493 |
| goto | 379 | 15.141 | 35.611 | 55.705 |
| waitForFunction | 35 | 4.646 | 20.973 | 145.914 |
| waitForTimeout | 215 | 13.191 | 26.179 | 101.980 |
| Other methods | 1,696 | 27.450 | 6.253 | 31.999 |

Method totals sum to 231.924 s, not the 225.973 s union: event waits can contain actions. Every method, including setup/teardown totals, is in `full-methods.csv`. Runtime counts include helper calls and loops; the owner's 1,245 source `expect(` calls and 16 source fixed waits are not runtime counts. There are also 1,187 teardown `waitForTimeout` calls, outside the table's call-phase denominator.

### Expectation retries

Installed Playwright **1.63.0** uses `retryWithProgressAndBackoff` with `[20, 50, 100, 100, 500]` ms, repeating 500 ms. It is not the separate `[100, 250, 500, 1000]` polling helper. The relevant code is `playwright/driver/package/lib/coreBundle.js:23990–24021` and `:24269–24300`. After an initial one-shot check it tries again immediately, then sleeps. Cumulative retry steps are 20, 70, 170, 270, 770, 1270 ms, and so on.

| Expect duration bin | Calls | Sum seconds |
| --- | ---: | ---: |
| Below 20 ms | 1,220 | 4.381 |
| 20–70 ms | 224 | 9.015 |
| 70–90 ms | 220 | 17.646 |
| 90–170 ms | 94 | 10.571 |
| 170–270 ms | 19 | 3.507 |
| 270–320 ms | 114 | 33.399 |
| 320–770 ms | 0 | 0 |
| 770–850 ms | 13 | 10.372 |
| 850 ms and above | 10 | 24.946 |

The clusters just after 70, 270 and 770 ms support a retry-step effect. They do not reveal when the app became ready. The model assigns each assertion its latest possible final sleep from that schedule and assumes readiness is uniform within it: half the final interval gives 22.490 s; zero to the full interval gives a 0–44.980 s envelope. Attempt overhead and real app latency can make this estimate too high. In particular, a 290 ms sign-in assertion can include about 210 ms of necessary password checking; it is not 290 ms of wasted polling. Both client languages use this same engine.

## Part B — Python versus TypeScript

Installed `@playwright/test@1.63.0` only in `/tmp/list-app-ba3-ts-PXs52e`; no repository dependency file changed and no browser was downloaded. Both installations have identical `browsers.json`, SHA-256 `545d52f8382c391e605562c330e9c1c534a16045898203037a49bb8bd769a946`.

Each test ran five times per driver, alone, serial, against the unchanged app. Driver order alternated between rounds. Both used a new context per session, the same viewport, selectors, assertions, trace settings, API seeding, database reset and teardown quiet check. TypeScript starts the original `TestServer` through a Python RPC bridge and calls its `reset_data()`; its final SQL assertion also uses that bridge. The timer includes context creation in the test body, but excludes fixtures, teardown and server/browser startup, as pytest's call timer does.

| Test | Python median call s | TypeScript median call s | TS change | Python / TS observed range s |
| --- | ---: | ---: | ---: | --- |
| `tags::test_tap_filters_the_items` | 0.723 | 0.725 | +0.3% | 0.709–0.789 / 0.708–0.791 |
| `items::test_add_restore_check_quantity_edit_and_undo` | 5.649 | 5.724 | +1.3% | 5.595–6.106 / 5.707–5.907 |
| `live::test_two_phones_see_each_others_changes` | 1.568 | 1.628 | +3.8% | 1.525–1.582 / 1.538–1.652 |

All ten traces per test have identical per-method counts after excluding screenshots and teardown polling. This includes 5, 58 and 11 browser assertions, respectively. TypeScript's API status checks and SQL check use the test runner's assertions where Python uses native `assert`.

Median single-test **process** wall times were Python/TS: 2.438/2.845, 7.476/7.995 and 3.367/3.886 s. These include different runner and bridge startup costs; they do not predict a six-worker whole-suite penalty. Five samples are not enough to resolve small differences. The last Python live run also had the added CPU snapshots; the other comparison runs used the earlier phase/server-only probe. It stayed within the other Python live timings.

## Speed ideas — not implemented

- Evaluate a same-condition animation-frame or mutation-driven wait for a common assertion pattern. Keep the same failure and timeout checks. The retry model suggests about 22 worker seconds, roughly 3.7 wall seconds at six perfectly balanced workers; the credible saving remains unmeasured and could be zero. It does not support a language rewrite.
- Consider the existing test-only low-cost bcrypt approach for **browser test servers only**, with production-cost security checks kept elsewhere. The tags sample spends 1.709 s in eight sign-ins, so the file has about 1.7 s of potential server-wait reduction, plus startup costs. This needs a separate proposal; no production hashing or browser test setup was changed here.

## Checks and first failures

- Full Chromium: 162 passed, existing 40 skipped. Tags measurements: 7 passed twice. Driver comparison: 15 Python and 15 TypeScript invocations passed. First traces and logs retained.
- First comparison command incorrectly anchored `--grep` at the start of the full Playwright title and selected no tests. Kept in `comparison-harness-error-1/`; fixed only the filter. No failing test was retried to make it green.
- Ruff first found an import issue and `pairwise` advice in the new analyzer. Fixed both without unsafe fixes.
- First required `uv run pytest -q`: **5 failed, 1,793 passed in 7.42 s**. One new synthetic analysis test exposed selection of the outer rather than nearest `popen-gw*` path; fixed the parser. The four other failures were unchanged documentation tests, with Zensical `TooManyOpenFiles` errors. The first worker stopped rather than rerunning unchanged checks to obtain green.
- After the parser fix, targeted analyzer checks: **5 passed**. Ruff formatting, lint and `ty` also passed. First outputs remain in `python-quality.txt` and `analysis-checks.txt`.
- Initial host diagnosis in `host-resource.txt`: `inotify_init1` returned errno 24 despite a process FD limit of 1,048,576; `fs.inotify.max_user_instances` was 128. The owner then raised that limit to 512 and authorized a new full quality check. The continuing worker verified the new value; it changed no host settings or other sessions.
- On 2026-11-14, ran under both locks: `uv run ruff format .`; `uv run ruff check --fix .`; `uv run pytest -q`; `uv run ruff format --check .`; `uv run ruff check .`; `uv run ty check`. **All exited 0; 1,798 tests passed in 6.94 s; 317 Python files unchanged by formatting.** Evidence: `resume-python-quality.txt`, 06:48:24–06:48:31 CET. No tracked file changed during these checks.
- Rechecked retained evidence without rerunning browsers: all 30 comparison exits are zero, all ten traces per test have matching API counts, and call medians agree with the table. Full-run trace count, phase totals and tags allocations also agree. Evidence: `resume-evidence-check.txt`.
- Reviewed the five-file final diff (`resume-final.diff`). No product code, existing test, dependency, shared bookmark or history changed. Reviewer `none` in the current worker instructions overrides the older continuation request for a separate review; no independent verdict is claimed. Acceptance remains the owner's next step, not part of this task. The report preview was not restarted.

## Evidence and retained files

Raw evidence: `.night-evidence/lr-347/lr-347.10.3/`. It includes `full*.{json,jsonl,csv,xml,txt}`, the full trace folder, server logs and parsed requests, all comparison traces, exact per-run metadata, the TypeScript sources and lockfile, first failures, quality output and final diff. The continuation adds `resume-python-quality.txt`, `resume-evidence-check.txt`, `resume-final.diff` and a closure handoff. The temporary npm installation is also left in place.

Tracked spike files: `browser_tests/ba3_probe.py`, `ba3_analyze.py`, `ba3_bridge.py`, `ba3_compare.py`, and `tests/test_ba3_analysis.py`. They are opt-in measurement code and five parser checks. Existing app and test code is unchanged. The sole unaccepted change is directly on the recorded integration baseline; it has no unfinished ancestors. The workspace and local bookmark remain for morning review.
