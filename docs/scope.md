# Scope

What stays true across tasks: the project's size, its risk level, the few
actions that need approval, and what agents may do without asking.

## Project

- A mobile-first list app for a small group (about five users). An MVP that
  grows slowly, one feature at a time.
- The owner is learning web development. Explain web concepts in simple terms.
- The stack is in [`ARCHITECTURE.md`](../ARCHITECTURE.md). Discuss stack changes
  before implementing them.

## Risk level

Ship and fix forward.

- The list data is not critical. Every deploy takes a backup first. If a deploy
  breaks something, even the database, we fix it or restore the backup.
- Work end to end: implement, run the automated tests, then propose the push.
  Do not add extra safety steps, rehearsals or staging.
- Automated tests are the evidence: pytest, the browser suite (Chromium,
  Firefox, WebKit for Safari) and the Android emulator suite where relevant.
- Keep manual checks to a minimum. Do not ask the owner to test on a phone,
  over Tailscale or in a staging environment before deploying. The owner sees
  changes live after the push.
- Ask for a manual device check only for very high-risk changes, such as a
  migration that could lose data or a change that could lock everyone out. Say
  why in one line.

## Gates

These need the owner's explicit approval. Anything not named here is ordinary
work within a selected task.

- **Deploy:** moving or pushing `main`. A push deploys production. Follow the
  [deployment checklist](deployment.md#deployment-checklist).
- **Accept work:** moving `integration` (except the docs-desk permission below).
  Approval to move `integration` does not approve a deploy.
- **Rewrite shared history:** rebasing feature lines onto `integration`, or
  changing another workspace's revision.
- **Start implementing** while we are only discussing. A direct request, a
  handoff that records approval, or a briefing agent passing on approval
  starts the work.
- **Stack changes** and deviations from [`ARCHITECTURE.md`](../ARCHITECTURE.md).
- **Retire** a superseded or partly done plan or other document, outside the
  completion rules below.

## Standing permissions

- Commit your own shared-docs edits on the docs desk and move `integration` up
  to them. Docs-only changes need no push.
- Create, use and remove your own jj workspace for a task.
- Delete a plan whose progress items are all checked, once its outcomes are
  preserved and incoming links are fixed. Name the deletion in the summary.
- Run tests, checks and read-only commands at any time. Verification is not
  approval, and missing approval does not block verification.
