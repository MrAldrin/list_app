# Testing ListR

Use tests to check observable app behavior, not only fixture setup or test counts.
The [scope](scope.md#risk-level) owns release risk and acceptance rules.

## Test layers

| Layer | What it checks | Main limit |
| --- | --- | --- |
| Python (`tests/`) | API authorization, data rules, transactions, migrations, and server helpers against disposable data | It does not run the browser UI. |
| Frontend (`frontend/src/**/*.test.ts`) | Client state, offline storage and queue rules, synchronization, and selected component behavior | Simulated browser APIs do not prove real engine behavior. |
| Browser (`browser_tests/`) | Real UI journeys, separate member/visitor sessions, live updates, offline behavior, and stale access across Chromium, Firefox, and WebKit | Local HTTP is not production HTTPS or a real phone installation. |
| Android (`android_tests/`) | Chrome and installed-app journeys on the dedicated emulator | It does not establish iPhone behavior. Run serially. |

## Commands and isolation

- Python commands and worker defaults: [README checks](../README.md#tests-and-code-checks).
  Required Python format, lint, test, and type checks: [agent rules](../AGENTS.md#python-quality-checks).
- Frontend setup and checks: [frontend guide](../frontend/README.md#checks).
- Browser setup, explicit worker counts, disposable servers, and traces:
  [browser guide](browser-testing.md).
- Device setup, serial execution, and cleanup:
  [Android guide](android-emulator-testing.md).

Run affected tests while editing. Run the required completion checks before
reporting a change as verified. Some Python route tests need a frontend build;
without it, they skip. Build first when checking those routes. Do not replace a
required engine or device check with a faster layer. Use only disposable
databases and test credentials.

## Reliability and measurement

Keep the first failure and its logs and traces. A pass on rerun is a flaky
outcome, not a clean first-run pass. Report failed tests, teardown errors,
intentional skips, and environment blockers separately. Do not add retries,
waits, or skips to hide failures.

Measure one suite at a time. Record the revision, command, engine, worker count,
and total elapsed time. Separate dependency setup and builds from test time.
Parallel per-test durations are worker time, not total elapsed time. Use repeated
comparable runs before claiming a speed improvement. The
[measurement record](background/test-suite-review.md) gives commands, findings,
and limits. Earlier speed evidence is [here](background/test-suite-speed.md).

## Known limits

- Personal-reminder settings browser checks remain deliberately paused until S3.
  Due-date and public-share checks remain active. See
  [P2 validation](background/reminders-p2-validation.md#deliberately-paused-browser-checks).
- Linux WebKit is the Safari check, not proof of real iPhone installation or OS
  behavior. Device acceptance rules remain in the [scope](scope.md#risk-level).
- Android coverage and benchmark changes need the decisions in the
  [speed plan](../plans/test-suite-speed.md#resume-here--remaining-work).
- Coverage percentages and passing counts do not establish assertion quality.
  The risk-led review is bounded; unreviewed areas are not declared complete.
