# Agent instructions: List app

## Startup

- This is a small web list app and an MVP that grows slowly. It is the owner's
  first web app. Explain web development in simple terms.
- Read the [backlog's current focus](plans/backlog.md#current-focus) before
  choosing work. Placement is not permission; a direct request is.
- [`docs/scope.md`](docs/scope.md) owns the risk level, the gates that need
  approval and the standing permissions. Do not restate them here.
- [`README.md`](README.md) owns the repo map and quick start.
  [`ARCHITECTURE.md`](ARCHITECTURE.md) owns the stack and its boundaries; if
  code deviates from it, tell the owner and agree which one changes.
- Follow best practice for Python web development. Split large tasks into
  small, testable chunks.
- When working in a new jj workspace, remind the owner of the
  [new workspace setup](README.md#new-jj-workspace) if `.env` is missing.

## Documentation and plans

Give each fact one home. Link to it instead of copying it.

- `README.md`: app introduction, quick start, repo map.
- `ARCHITECTURE.md`: stack, boundaries, security decisions and major UX
  decisions. Keep implementation mechanics in linked docs.
- `docs/`: current behavior, contracts, and operational guides. Update the
  affected docs when behavior changes. `docs/scope.md` is the standing scope.
  Start readers at [`docs/index.md`](docs/index.md).
- The root [`ARCHITECTURE.md`](ARCHITECTURE.md) is authoritative. The Zensical
  preview reads it directly; it does not maintain a second copy. The
  [README's local preview](README.md#documentation-preview-local-only) explains
  the commands and content/privacy limits. Preview configuration does not grant
  permission to publish.
- `docs/background/`: evidence and reasoning behind current docs, such as
  investigations, measurements, and audit logs. These files may be long. They
  are never the primary source for current behavior; current docs link to them.
- `docs/superpowers/handoffs/`: short-lived notes that carry one task into a new
  session. The receiving agent deletes the note after reading it.
- Local Beads: the one task-status agenda. Follow the [task guide](docs/beads.md).
  `plans/backlog.md` is the entry point; plans keep supporting detail.
- `plans/<item>.md`: details for one larger item, not a second queue. Clearly
  distinguish planned, implemented, and verified work. A plan is not evidence
  that a feature exists. Put progress tracking at the bottom.

### Plan lifecycle

- Start every plan with a lifecycle line under its title: `Lifecycle: temporary`
  (approved start-to-finish work) or `Lifecycle: tracked` (open-ended or
  multi-session work). Tell the owner which lifecycle applies. Treat unlabelled
  plans as `tracked`.
- Before removing a plan, move durable decisions to `AGENTS.md`, `docs/`, or the
  backlog. Move evidence worth keeping to `docs/background/`. Track unfinished
  work in the backlog, and fix incoming links.
- When every progress item is checked and the conditions above hold, the agent
  that finished the work deletes the plan (temporary or tracked) in its own
  final jj change. Do not ask first. Name the deletion in the summary.
- Retiring other documents (superseded or partly done plans) is a
  [gate](docs/scope.md#gates). Retain plans with unresolved work.
- Keep documentation updates scoped to the task; this policy does not authorize
  a repository-wide cleanup.

### Quality rules for top-level docs

Applies to `README.md`, `ARCHITECTURE.md`, and top-level files in `docs/`.

- Include current behavior and decisions only. Put progress logs, test counts,
  dated evidence, and experiment history in `docs/background/`, and link to them.
- Keep docs short: aim for about one screen. Checklists and step-by-step guides
  may be longer.
- Use plain language and short sentences. State each fact once; do not stack
  caveats.
- Put unverified or pending work in the backlog, not in the doc.
- If a doc has grown past these rules, split detail out to `docs/background/`
  instead of adding more.

## Jujutsu development baseline

Approval rules for these steps are [gates in the scope](docs/scope.md#gates).

- `integration` marks accepted work: "keep this, build on it". It does not
  mean the work is deployed. It must include `main`. If it is behind, fix the
  baseline with approval before starting work. Start independent work
  from `integration` when it is ahead of `main`; otherwise start from `main`.
  Continue existing work on its own line.
- `main` is the production line. Pushing it deploys Railway. The owner runs the
  [deploy script](docs/deployment.md#deployment-checklist), which moves `main`.
  Feature bookmarks mark work that is not yet accepted. There are no other
  shared bookmarks. Do not repurpose these.
- `integration` may be ahead of `main`. That is normal, not a to-do. Docs-only
  work goes out with the next code push. To see what a push would deploy, run
  `jj diff -r main..integration --stat`.
- Before starting work, inspect `jj status`, `jj bookmark list`, and the graph.
  Preserve existing workspace edits. If `integration` is missing or conflicted,
  ask instead of choosing another baseline silently.
- When accepting work, point `integration` at the completed change, not the
  empty working-copy child (`jj bookmark set integration -r @-` when `@` is
  empty). First inspect the current target and ancestry. Do not overwrite
  unrelated accepted work.
- Never rebase another agent's active work merely to tidy the graph.

## Workspace coordination (trial)

This is a trial, not a permanent workflow. Keep it lightweight; discuss relaxing
these guardrails after we have tried them. Do not remove them automatically.

- Before editing a new task or session, briefly confirm the target repo, scope,
  workspace, and known concurrent work with the owner. If the owner or handoff
  already makes these clear, acknowledge that instead of asking again.
- Treat `/home/hsa/projects/list_app` as the coordination workspace, not the
  `main` production line. Multiple agents may coordinate there, but agree who
  is writing each shared file before editing it.
- For each new task, every agent creates its own jj workspace based on the
  current development baseline above and does all implementation there. Never
  share an implementation workspace with another agent. Keep feature-specific
  docs and tests with the feature.
- When the task's work is integrated, the agent that created the workspace
  removes it (`jj workspace forget <name>`, then delete its folder). Leave
  workspaces that existed before this rule alone.
- Phone testing uses port 8080, one workspace at a time. Stop your
  `serve_svelte_local.py` server when you are done; if the port is in use, ask
  the owner rather than stopping another agent's server.
- The default workspace is the shared docs desk. It always sits on top of
  `integration`, so the graph stays one line: `main`, accepted work,
  `integration`, open work.
  - Edit shared backlog and plan files there, never divergent copies in a
    feature workspace. Check current ownership and status first.
  - Commit your own docs edits right away, naming only your files
    (`jj commit plans/x.md -m "..."`), so two agents' edits never share a change.
  - A committed shared-docs change is accepted: move `integration` up to it
    (a [standing permission](docs/scope.md#standing-permissions)).
  - After `integration` moves for any reason, rebase the desk's open changes
    onto it (`jj rebase -s <first open change> -d integration`).
  - A finished feature is rebased onto `integration` from its own workspace;
    then `integration` moves to its tip with approval.
- Pi agents can use Pi Intercom to coordinate. Do not assume Claude Code is
  reachable through it. Use an owner relay or an agreed shared handoff for
  cross-tool coordination.
- Push back when task ownership, overlapping edits or the integration baseline
  is unclear. Explain the concrete risk and propose the smallest safe next step.

## Local task tracking

- All jj workspaces use `/home/hsa/projects/list_app/.beads`. Follow the
  [local task guide](docs/beads.md). Run an explicit primary-store `where`
  check before writes. Do not initialize a separate code-workspace store.
- Use a unique full-session actor and an atomic claim only for approved work.
  Stop on ownership rejection; guard closure by the actual claimant and status.
  Source groups and historical owners are not active claims or approval.
- Preserve the native store, private runtime evidence and sibling gate lock.
  Use native backup/recovery, not JSONL-only recovery. Existing integration,
  shared-docs and deployment gates stay.
- Sync: follow "Sync with GitHub" in the shared PRIME.md. Beads data remote: MrAldrin/list_app-beads (private).

## Tools

- Packages: `uv` (use the dev group if only for development).
- Formatting and linting: `ruff`.
- Version control: jj with git backend. Prefer jj workflows.

## Python quality checks

Before reporting a task complete when Python files have changed, run:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest -q
```

Then verify that formatting, linting and types are clean (`ty` checks `src/`
only):

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
```

Review any remaining Ruff issues rather than using unsafe fixes automatically.
