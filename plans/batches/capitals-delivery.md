# Capitalization delivery

Lifecycle: temporary

## Brief (Lead-owned)

- Implement the approved item-name capitalization decision using `plans/item-name-capitalization.md`, after its migration plan was written and reviewed. Preserve display case, trim, and prevent case-insensitive duplicate items; retain existing names/data, offline operations and documented API compatibility. No app deployment or bookmark movement.
- Match existing app's Unicode-aware Python `lower()` duplicate semantics unless code review finds a concrete inconsistency that threatens correctness; do not silently introduce a broader casefold policy. Migration collision must fail safely without merging/deleting data. Handle browser/server normalization consistency and queue replay, and escalate actual ambiguous data-loss/compatibility conflicts.
- Owner approved implementation, including necessary documentation and architecture updates for this explicit UX change. Keep unrelated features and owner-managed security-small untouched. Full relevant checks: project Python checks, frontend check/lint/test/build, real-browser suites (Chromium/Firefox/WebKit), migrations and offline replay. Independent fresh-context review before handoff.
- Report newly necessary product questions to Lead with recommendation; do not ask owner about normal implementation choices. Do not edit shared backlog, shared decisions, or temporary plans; Lead owns them on docs desk and tracks implementation. Deliver all feature-specific docs/tests with code.

## Assignment

- Base `klzmknyt` d60722d4; integration destination Lead's default line. Owner authorized integration into default but explicitly forbids moving integration/main, pushes or deploys. Conductor runs in Lead-owned agent workspace `/home/hsa/projects/tmp-listr-capitals`; Lead owns entry integration and cleanup. Conductor owns worker/reviewer workspaces and cleanup. One writer per workspace.
- Bounded children permitted; Luna xhigh then Sol medium if needed. Conductor GPT-6.1 Terra medium. `.env` missing: use test credentials, no secrets copied. Report to Lead via intercom.

## Status (Conductor-owned)

Active. Conductor session `01a18ea9-0910-7616-879b-19e176793495`. Worker completed `lukostum` in conductor-owned `tmp-capitals-impl` (`/home/hsa/projects/tmp-capitals-impl`); independent read-only review is active. Next: resolve review, integrate, and run full combined checks. Conductor owns child workspace cleanup.

## Closeout (Conductor-owned)

Pending.
