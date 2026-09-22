# AI Agent Configuration: List app

- This project should create a MVP of a list app for the web. 
- It should be simple, and slowly add more features.
- This is my first web app. So explain the ways of web development in simple terms for me to learn along the way.
- Dont implement anything before I explicitly tell you to. 
- Modular Implementation: Split large tasks into small, testable chunks.


## User preferences for agent answers

- Short answers
- Use bullet points where it makes sense
- Dont always agree with the user, push back if you disagree
 
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
- `docs/`: Current behavior, technical details, and operational guides. Update affected references when behavior changes; distinguish verified behavior from pending checks.
- `plans/`: Proposed work, decisions, implementation steps, and progress tracking at the bottom. Clearly distinguish planned, implemented, and verified work; a plan is not evidence that a feature exists.
- `plans/backlog.md`: Unfinished or deferred work, with links to detailed plans where useful. Do not use it as an operational reference or a permanent completed-work log.
- Keep each fact in one primary document and link to it rather than copying it across files.
- When work finishes, update current references, remove or mark the corresponding backlog item complete, and record any remaining work or verification separately. Remove completed backlog entries during an approved cleanup; version control preserves their history.
- Retire a completed or superseded plan only after durable decisions have moved to current references, remaining tasks are tracked, and incoming links are updated. Retain plans with unresolved work. Delete retired documents only with user approval or as part of an explicitly approved cleanup; version control keeps the history.
- Keep documentation updates scoped to the approved task; this policy does not authorize a repository-wide cleanup.


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
