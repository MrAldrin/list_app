# Claude Code instructions

@AGENTS.md

## Cloud sessions (no jj)

Claude Code on the web may not have jj. There, use git instead:

- Start each task from the `integration` branch, on its own new branch.
- Open a pull request into `integration`. Never push or merge into `main`;
  pushing `main` deploys production.
- One task per branch. Run the checks in `AGENTS.md` and `npm --prefix frontend run lint` before calling it ready.
