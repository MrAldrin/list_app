# AI Agent Configuration: List app

- This project should create a MVP of a list app for the web. 
- It should be simple, and slowly add more features.
- This is my first web app. So explain the ways of web development in simple terms for me to learn along the way.
- Dont implement anything before I explicitly tell you to. 
- Modular Implementation: Split large tasks into small, testable chunks.


## Technical Stack ideas
The technologies used can be found in ARCHITECTURE.md under Core Architecture Decisions. But if we need to make changes to this, tell me.


## Repo structure ideas:
Follow best practise for python web development.
We also have these extra files and folders:
- src/: the app code. main.py is the entry point
- ARCHITECTURE.md: A markdown file where we keep the high lever architecture. We look back at this document to see if we have deviated from the achitecture. If that happen you must tell me, and we have to either change our direction or update the arhitecture file to match.
- plans/: 
    - A special folder that you should use if you make longer plans.
    - We will often iterate on a .md file together before implementing the plan. 
    - The bottom of the files should contain tracking of progress for that plan.



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
