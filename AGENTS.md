# AI Agent Configuration: List app

- This project should create a MVP of a list app for the web. 
- It should be simple, and slowly add more features.
- This is my first web app. So explain the ways of web development in simple terms for me to learn.
- Don't implement while we are only discussing. Start work when:
  - the user asks for it directly;
  - a handoff document says the user approved starting it; or
  - you are a subagent, and the agent that briefed you passes on the user's approval.
- Modular Implementation: Split large tasks into small, testable chunks.
- GitHub `main` deploys the live Railway app when pushed. Get explicit approval before moving or pushing `main`; treat a push as a production deployment and follow the [deployment checklist](docs/deployment.md#deployment-checklist). Pushes to `main` are only allowed inside the [deploy window](docs/deployment.md#deploy-window).

- When working in a new jj workspace, remind me of the [new workspace setup](README.md#new-jj-workspace) if `.env` is missing.

## Technical Stack ideas
The technologies used can be found in ARCHITECTURE.md under Core Architecture Decisions. But if we need to make changes to this, tell me.


## Repo structure ideas:
Follow best practice for python web development.
We also have these extra files and folders:
- src/: the app code. main.py is the entry point
- ARCHITECTURE.md: A markdown file where we keep the high level architecture. We look back at this document to see if we have deviated from the architecture. If that happens you must tell me, and we have to either change our direction or update the architecture file to match.
- plans/: 
    - A special folder that you should use if you make longer plans.
    - We will often iterate on a .md file together before implementing the plan. 
    - The bottom of the files should contain tracking of progress for that plan.



## Documentation lifecycle
- `README.md`: App introduction, quick-start instructions, and links to detailed documentation.
- `ARCHITECTURE.md`: High-level stack, boundaries, security decisions, and major UX decisions. Keep implementation mechanics in linked reference docs; discuss architectural deviations with the user.
- `docs/`: Current behavior, technical details, and operational guides. Update affected references when behavior changes. Top-level docs must meet the quality rules below.
- `docs/background/`: Supporting detail for docs and plans: investigations, measurements, evidence, audit logs, and the reasoning behind decisions. May be long. Never the primary source for current behavior; link to the top-level doc for that.
- `plans/`: Proposed work, decisions, implementation steps, and progress tracking at the bottom. Clearly distinguish planned, implemented, and verified work; a plan is not evidence that a feature exists.
  - Every plan starts with a lifecycle line under its title: `Lifecycle: temporary` (a checklist for approved start-to-finish work, deleted when done) or `Lifecycle: tracked` (open-ended or multi-session work, kept until retired with approval). Choose the label when writing the plan and tell the user which one. A plan without a label counts as `tracked`. `plans/backlog.md` has no label.
- `plans/backlog.md`: Unfinished or deferred work, with links to detailed plans where useful. Do not use it as an operational reference or a permanent completed-work log.
  - Sections: **Next** (committed, in order, top first, no size limit), **Later** (agreed, no date), **Ideas** (no promise), **Manual checks** (production and device checks for the user).
  - Each item starts with a tag listed at the top of the backlog, then a short description and a link. Keep details in the linked plan or doc.
  - "Do this next" goes at the top of Next. For any other request to add an item, ask which section it goes in, and where in Next if chosen.
  - Mark an item being worked on across sessions with `(in progress)`. Move items between sections only when the user decides.
- Keep each fact in one primary document and link to it rather than copying it across files.
- When work finishes, update current references, remove or mark the corresponding backlog item complete, and record any remaining work or verification separately. Remove completed backlog entries during an approved cleanup; version control preserves their history.
- Delete a `temporary` plan in its own final jj change, without asking, only when all of these hold: it says `Lifecycle: temporary`; every progress item is checked; its durable decisions have moved to `AGENTS.md`, `docs/`, or the backlog; and no other file links to it (fix links first). Name the deletion in the final summary.
- Retire a `tracked` (or unlabeled) completed or superseded plan only after durable decisions have moved to current references, remaining tasks are tracked, and incoming links are updated. Move evidence or reasoning worth keeping to `docs/background/`. Retain plans with unresolved work. Delete retired documents only with user approval or as part of an explicitly approved cleanup; version control keeps the history.
- Keep documentation updates scoped to the approved task; this policy does not authorize a repository-wide cleanup.

### Quality rules for top-level docs
Applies to `README.md`, `ARCHITECTURE.md`, and top-level files in `docs/`.
- Current behavior and decisions only. No progress logs, test counts, dated evidence, or experiment history; put those in `docs/background/` and link to them.
- Short: aim for about one screen. Checklists and step-by-step guides may be longer.
- Plain language and short sentences. State facts once; do not stack caveats.
- Unverified or pending work belongs in `plans/backlog.md`, not in the doc. A short "Pending checks" link to the backlog is enough.
- When editing a top-level doc, keep it within these rules. If it has grown past them, split detail out to `docs/background/` rather than adding more.


## Jujutsu development baseline

- `integration` marks the accepted development baseline. It means “keep this work”, not “production-tested”. Start new independent work from this bookmark (`jj new integration`); continue existing work on its own line.
- `main` is the production deployment line. `main-staging` marks a tested deployment candidate. Feature bookmarks mark work not yet integrated. Do not repurpose these bookmarks.
- Before starting work, inspect `jj status`, `jj bookmark list`, and the graph. Preserve existing workspace edits. If `integration` is missing or conflicted, ask rather than choosing another baseline silently.
- Move `integration` only with explicit user approval to accept completed work. Point it at the completed change, not an empty working-copy child. Do not overwrite unrelated accepted work; inspect the current target and ancestry first.
- Rebase existing feature lines onto `integration` only with user approval and coordination with any agent using them. Never rebase another agent’s active work merely to tidy the graph.
- Updating `integration` does not authorize moving `main` or `main-staging`, pushing, or deploying. Existing deployment approval and deploy-window rules still apply.

## Tools:
- Packages: Use uv (use the dev group if only for development).
- Formatting: Use ruff.
- Version control: jj with git backend. Prefer jj workflows.

## Python quality checks
Before reporting a task complete when Python files have changed, run:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest -q
```

Then verify that formatting and linting are clean:

```bash
uv run ruff format --check .
uv run ruff check .
```

Review any remaining Ruff issues rather than using unsafe fixes automatically.
