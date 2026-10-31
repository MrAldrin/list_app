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

Review-ready for Lead integration. Conductor session `01a18ea9-0910-7616-879b-19e176793495`. Worker workspace `tmp-capitals-impl` was integrated into this batch line and removed. Lead owns entry workspace and final integration.

## Closeout (Conductor-owned)

- Delivered `lukostum`, `ysnysyuv`, and `xmsktuos`: case-preserving names, safe migrations and Unicode key rebuild, offline reconciliation, and documentation. Fresh independent review found no remaining issues; subsequent changes were formatting only.
- Combined checks: 1,451 Python tests, Ruff and ty; frontend check, 641 tests and build; 366 browser tests across Chromium, Firefox and WebKit. An earlier browser run had two failures and two teardown errors; the three affected cases passed individually and the full suite passed on rerun.
- Frontend lint passes Prettier but has five existing navigation ESLint errors, reproduced on the exact parent with the same dependencies. npm reported five dependency advisories (four low, one high); no audit fixes applied.
- A plain SQLite connection needs the documented app function to insert or rename items; backup and restore paths were reviewed. A Unicode-key collision stops startup without merging data. Browser matching is provisional until server reconciliation.
- No bookmarks moved or deployment performed. Lead retains shared-plan lifecycle and final integration.
