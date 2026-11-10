# Stack research runner: preparation evidence

Preparation bead: `lr-fgr`. Research epic: `lr-zja`.
This records preparation on 2026-11-10, not completed Phase 1 research.

## Checks

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

See the [operator guide](../stack-research-runner.md) for start, status, stop and
resume. No acceptance, deployment or rewrite was performed during preparation.
