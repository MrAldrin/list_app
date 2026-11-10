# Stack research runner: preparation evidence

Preparation bead: `lr-fgr`. Research epic: `lr-zja`.
This records preparation on 2026-11-10, not completed Phase 1 research.

## Original non-interactive preparation (`lr-fgr`)

- Full Python suite: 1,820 passed, no skips, with the frontend build present.
- Ruff format, Ruff lint and ty: passed. ty covers `src/`, as configured.
- Node guard tests: four passed.
- Frontend build: passed. No frontend source changed.
- Synthetic queue tests cover sequence, no Phase 2, failed review, ownership,
  prerequisite rejection, stop-before-close and retained closure recovery.
- A real short-lived child test checks that stop terminates the owned process.
- Live Pi no-tools canaries verified Sol 6.1/high, Luna 6/xhigh and Terra 6.1/low
  from persisted session events.
- A live synthetic tool check verified the runtime doctor, a permitted file
  read, a blocked synthetic file read and public Effect documentation retrieval.
  No research bead was claimed or executed by these checks.

## Review and fixes

Fresh Luna/xhigh review found a stop-before-close gap, unrestricted file reads
and stale status. The runner now has the final stop check, a manifest-scoped
read guard, live-lock status and retained-child detection.

Fresh Terra 6.1/low review found a missing loaded-runtime-doctor gate. The guard
now blocks source reads until that diagnostic succeeds. A targeted review
confirmed the fix against code and live smoke evidence. Its cached-stage caveat
was also fixed: reuse requires guard and doctor receipts. A regression test
checks missing receipts. Both reviewers' models and tiers were verified from
persisted session records.

The initial synthetic Pi response completed but its process stayed open.
The runner now observes `agent_settled`, then ends the owned idle process group.
Active research has no time limit. The guard is not an OS sandbox; generic web
queries still require judgment and are not guaranteed free of private content.

Private live evidence is retained at
`~/.local/share/list-app-stack-research/preparation/`.
Reports and workspaces from the actual run will be retained for owner review.

## Interactive Zellij revision (`lr-nav`)

The owner then required visible interactive Pi panes, one agent at a time, with
automatic closure after completion. The revised runner uses a normal Fish shell
in each new no-focus tab, verifies the Pi session and pane, then releases the
research prompt. It does not use print, JSON or RPC execution modes.

A disposable live test verified Sol 6.1/high in TUI mode, matching session/cwd/
pane identity, a completed synthetic response, return to the normal shell and
closure of the owned pane and empty sidebar tab. An earlier failed test exposed
Fish's startup directory change; explicit `cd` plus cwd verification fixed it.
The failed and successful evidence are retained privately under
`~/.local/share/list-app-stack-research/preparation/interactive/`.

Updated checks: 1,827 Python tests and five Node guard tests passed. Ruff format,
Ruff lint and ty passed. Unit tests cover shell-first launch, explicit pane
ownership, no-focus tabs, cwd correction, cleanup, readiness rejection, no
closure of user-added panes, and direct handling of a typed stop request.

The owner changed all reviewer assignments to Sol 6.1/low. Both review routes,
their canary and regression assertions now use that pair. A fresh Sol 6.1/low
review found no issues in the interactive runner, cleanup, stop behavior or
model routing. Its actual model and tier were verified from the saved session.
The full checks above were rerun after the model-routing changes. A final local
check also corrected lease renewal to use native `bd heartbeat`, rather than
an idempotent claim. A regression test verifies that command; renewal runs at
each stage start and every two minutes during work.

See the [operator guide](../stack-research-runner.md) for start, status, stop and
resume. No acceptance, deployment, rewrite or Phase 1 execution was performed.
