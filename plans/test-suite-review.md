# Test-suite review and improvement

Lifecycle: tracked

## Status and approval

Execution is approved within this brief and the [overnight run limits](night-run.md).
That record owns the approval, sequencing, stack destination, and operating limits.
Record the task owner, workspace, and effective model settings below at dispatch.

This is one task in the [backlog](backlog.md#next). The
[test-suite speed plan](test-suite-speed.md#resume-here--remaining-work) is
supporting material, not a second queue. Its completed work and unresolved
Android decisions remain valid.

## Outcome

Identify the most important weaknesses in the test suite. Review first, then
make a bounded set of clear improvements to tests and test helpers. Add missing
high-value coverage without building an elaborate test framework. Measure the
cost of the suite and leave a short decision list for the owner.

Success means better evidence about app behavior, not more tests, a higher
coverage percentage, or a claim that every assertion was reviewed overnight.

## Priorities and review scope

Inventory Python tests, frontend unit/component tests, browser tests, and the
Android suite. Deep-review the highest-risk behavior first:

1. Permissions, room/share boundaries, and access revocation.
2. Saved data, deletion/restore, and data integrity.
3. Offline queues, synchronization, reconnects, and conflicts.
4. Core list operations and the browser journeys that connect them.
5. Lower-risk presentation and convenience behavior as time permits.

Build a compact map:

**Behavior → risk → existing tests → weakness → proposed action.**

For reviewed tests, ask:

- Does the test exercise our app and assert an observable result?
- Could the app be broken while the test still passes?
- Does it assert fixture setup, language behavior, or framework internals instead?
- Does its expected result merely repeat the production calculation?
- Do mocks hide the integration or failure mode that matters?
- Would a harmless refactor break it?
- Does another test cover the same behavior, or protect a different boundary?

An item-count assertion is not inherently weak. Counting items after app save,
reload, or synchronization can be useful. Counting an array created only by
the test does not establish that the app works.

Use the lowest useful layer for detailed rule checks. Retain browser tests
where browser behavior or end-to-end wiring adds confidence. Do not enforce a
fixed ratio of unit, integration, and browser tests.

### Reliability

Investigate date-dependent assumptions, shared state, order dependence,
arbitrary sleeps, unawaited work, and test cleanup. Investigate the WebKit
sign-in failures seen during reminder work; passing on rerun does not prove
that a failure is harmless or that the app is correct.

Where needed, compare isolated, grouped, serial, and parallel runs. Separate
possible app defects from harness defects and resource contention. Retain the
first failure, traces, and rerun outcomes. Report a rerun pass as flaky, not as
a clean first-run pass.

Existing P2 evidence is described in
[its validation record](../docs/background/reminders-p2-validation.md).
The 120 engine-expanded settings skips are deliberate until S3. Inventory and
report them; do not enable unfinished reminder settings or remove these skips
as part of this task.

### Runtime and test value

Use existing pytest and frontend reporting first. Do not add a profiling
service or permanent benchmarking framework. Consult the
[previous measurements](../docs/background/test-suite-speed.md) before
repeating an experiment.

Record the revision, machine, commands, browser engines, worker count, and
whether a run included cold setup/builds. Measure total wall-clock time and,
where available, setup, execution, and cleanup separately. Do not sum parallel
test durations and present that as elapsed runtime.

Use comparable before/after runs. Repeat the baseline and candidate measurements
when claiming an improvement; use at least three comparable samples for a
claimed speed improvement where affordable. Report the median and range, and
state where there are too few samples. Do not run competing full-suite jobs on
the same machine during measurement.

Provide a runtime-versus-value table for expensive tests or groups:

| Test or group | Layer/engine | Measured cost | Value | Unique protection | Reliability | Action |
| --- | --- | --- | --- | --- | --- | --- |

Use **Critical**, **Important**, or **Supporting**, with a short reason based on
the impact of the bug caught. Value is not determined by runtime or test count.
A slow critical test is not automatically a removal candidate.

Coverage reports may help find untested paths. They do not establish useful
assertions. No percentage target or mandatory whole-project mutation score.

## Work sequence

1. Inspect the current baseline, instructions, existing reports, and test setup.
   Record existing failures/skips before changing tests.
2. Inventory the suite and collect a runtime baseline. Map high-risk behaviors
   to tests. State which areas get deep review and which get only a scan.
3. Classify findings using the two buckets below. Prioritize a small batch of
   high-value changes instead of starting a broad rewrite.
4. Implement and verify that batch. Keep behavior-focused tests and relevant
   helper fixes in small, reviewable changes. Repeat with another batch only
   if time and resources allow.
5. Obtain fresh independent review. Address findings and rerun affected checks.
6. Run completion checks, write the testing guide and evidence report, and
   prepare the morning handoff. Reserve time for verification and handoff;
   do not spend the whole window starting more fixes.

### Bucket A — implement within the approved run

- Fix clear defects in tests or test helpers.
- Strengthen weak assertions and add missing high-value behavior checks.
- Fix isolated, evidence-backed reliability problems in test infrastructure.
- Improve runtime without weakening assertions, isolation, password-hashing
  fidelity, or browser/device coverage.
- Document the test layers and reproducible measurement commands.

### Bucket B — recommend for an owner decision

- Remove or consolidate scenarios, assertions, or browser/device coverage.
- Change test tiers, release gates, or when required checks run.
- Perform large test rewrites or introduce new frameworks/dependencies.
- Change product code, product behavior, production settings, or architecture.
- Resolve uncertain duplication or disputed test value.
- Change Android scenarios or run emulator benchmarks. These still need the
  decisions in the existing speed plan.

For each Bucket B item, give the problem, evidence, expected benefit, protection
that could be lost, and a recommendation. Do not silently implement it.

## Authority and operating limits

Once execution is explicitly approved, the assigned owner may make Bucket A
changes to tests and test helpers in an isolated jj workspace. Execution approval
does not accept the resulting code or approve deployment.

- Follow repository scope, workspace, and quality-check rules.
- Do not change product code to make a test pass. For a discovered app bug,
  retain a minimal reproducer or failing test on a clearly marked separate
  change and report it. Do not hide it in an otherwise passing result.
- Do not skip, delete, weaken, or mark failing tests as expected failures to get
  green. No added retries, arbitrary sleeps, or longer timeouts as substitutes
  for finding a cause.
- Do not remove real coverage, change release gates, or disable an engine.
- No new dependencies, external service enrollment, production data, deployment,
  push, bookmark moves, parked-feature rebases, or unrelated jj cleanup.
- Use disposable data. Put browser artifacts in workspace-local paths. Keep
  failed-run evidence; remove disposable passed-run output when needed.
- Shared backlog/plan changes belong on the coordination docs desk, with an
  agreed write window. Source/test edits belong in the implementation workspace.
- If delegated, give each concurrent writer a separate jj workspace. Require a
  fresh independent reviewer to inspect the actual diffs and evidence.
- Do not assume unlimited overnight time or resources. Agree the work window,
  stop time, concurrent-worker limit, and artifact budget before launch. Stop
  safely on an authority or environment blocker and leave a usable handoff.

## Verification and acceptance

- For selected high-risk new or strengthened tests, deliberately break the
  relevant behavior in a disposable revision. Show that the test fails for the
  intended reason, then restore the code and show it passes. Log the mutation,
  command, and result. Leave no deliberate fault in delivered code.
- Reproduce reliability failures before claiming a fix. Repeat relevant runs
  afterward; state the confidence limits if a cause remains unresolved.
- Run targeted checks after each batch and full required completion checks on
  the final candidate. Follow AGENTS.md for Python changes and the documented
  frontend/browser commands. Read and report the actual exit status.
- Run the three-engine browser suite if browser tests or shared browser fixtures
  change. Keep Android execution outside this pass unless separately approved.
- Independent review must check coverage preservation, assertion quality,
  measurement validity, and whether the reported scope matches actual work.
- Report failures, flakes, and skips separately. Existing failures are not
  permission to obscure a new one. If a final gate fails, report the candidate
  as incomplete or awaiting a decision, not fully verified.

## Documentation and morning handoff

Create a concise `docs/testing.md`, linked from the docs hub. Explain what
Python, frontend, browser, and device tests prove; link the existing command
and device guides instead of duplicating them. Describe current execution rules,
known limits, and important coverage gaps. Do not present proposed tiers as
current policy or require extra manual phone acceptance.

Put dated findings, runtime tables, commands, fault-injection evidence, and
review results in `docs/background/test-suite-review.md`. Link it from the
testing guide. Keep durable behavior in current docs, not this task plan.

The morning handoff must contain:

- Changes delivered, ordered by risk addressed, and their change IDs.
- Deep-reviewed areas versus inventory-only areas and what remains unreviewed.
- Important coverage added or strengthened, with deliberate-breakage evidence.
- Before/after runtime and the value/cost table, with measurement limitations.
- Exact check results, failures/flakes/skips, and independent-review disposition.
- Bucket B decisions, each with a recommendation; unresolved app bugs separately.
- Workspace/agent ownership, retained artifact locations, and the next action.

## Research basis

These are guidance sources, not a requirement to adopt their tools or workflows:

- [Google: code coverage best practices](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html): use coverage to find gaps, not to prove test quality.
- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html): behavior-focused tests and confidence at the appropriate layer.
- [Playwright best practices](https://playwright.dev/docs/best-practices): visible behavior, isolation, and condition-based assertions.
- [Playwright retries](https://playwright.dev/docs/test-retries): distinguish first-run passes, retry passes, and failures. This project's pytest harness needs its own reporting; do not assume Playwright Test configuration applies.
- [pytest duration reporting](https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration): start with built-in timing tools.

## Execution record

- Priority, difficulty, and selected Conductor: see the [backlog](backlog.md#next).
- Approval: recorded in the [overnight run](night-run.md#approval-and-outcome).
- Task owner/session and effective model/thinking verification: pending.
- Workspace and child ownership: not assigned.
- Work window, concurrency, and artifact budget: [overnight run limits](night-run.md#run-limits-and-defaults).

## Progress

- [x] Record the proposed scope and merge the backlog agenda items.
- [x] Owner approves the execution brief and run limits.
- [ ] Assign task and child ownership.
- [ ] Inventory the suite, map high-risk behavior, and measure a baseline.
- [ ] Review and classify findings; implement bounded Bucket A improvements.
- [ ] Independently review and verify the final candidate.
- [ ] Write the testing guide, evidence report, and morning handoff.
- [ ] Record unfinished decisions in the backlog and complete workspace cleanup
  after acceptance. Retire this plan only when its lifecycle conditions hold.
