# Named item groups delivery

Lifecycle: temporary

## Brief (Lead-owned)

Implement Heming's authorized named item groups using `plans/named-item-groups.md` and `plans/decisions-for-heming.md`. Allow room users to create and reuse named groups on lists; one tap adds the group, skipping all existing matches including checked items. Do not uncheck existing matches. Use per-item retry-safe operations with clear partial results, concurrency-safe server checks, offline queue/reconciliation and UID remapping as in the reviewed plan. Cached groups may be used offline; management can require connection. Public-share-only access must not expose room catalog. If this cannot be implemented safely under current architecture, report blocker and options before expanding scope.

Base `mutymmln` 864b271b; integration destination default line. Owner approved integration on default but forbids moving integration/main, pushes and deployment. No unrelated work, AI or changes to security-small. Other planned features are not in this batch. Follow architecture and API compatibility/version gates; update feature docs and tests, including auth, live updates, offline replay, UID mapping, partial failures and limits. Group storage, feed/snapshot and server operations must not lose existing data. No shared backlog/plans/decisions edits: Lead owns those files.

Full frontend, Python and browser checks plus fresh independent review required; report exact results, retained artifacts, failures and limits. Owner delegated ordinary design choices; escalate genuine semantic, security, loss or scope ambiguity with recommendation. Prior full combined browser run had two failures (Firefox sign-in, WebKit offline navigation); both passed isolated; do not claim that run passed.

## Assignment

Conductor uses GPT-6.1 Terra medium; bounded children Luna xhigh, escalate Sol medium if needed. Lead owns entry workspace `/home/hsa/projects/tmp-listr-groups`, integration and cleanup; Conductor owns child workspaces. One writer per workspace. `.env` absent; tests use isolated credentials, no secrets copied. Report to Lead via intercom.

## Status (Conductor-owned)

Review-ready. Implementation `xxktorwz` is integrated into the batch workspace. The Conductor removed its child workspace after checks; Lead owns final integration and entry workspace cleanup.

## Closeout (Conductor-owned)

- Delivered `xxktorwz` (5702e7ce): room groups, online management, retry-safe member adds, offline reconciliation, tests and feature docs. Independent review of the exact diff found no remaining issues after fixes.
- Combined checks: 1,481 Python tests, 660 frontend tests and 378 browser tests passed. Python formatting, lint and type checks, frontend lint, Svelte checks and build passed. Browser log: `/tmp/groups-combined-browser.log`.
- An earlier post-review browser run had one WebKit offline service-worker failure and teardown error; six isolated retries and its 30-test module passed. Root cause unproven. Logs: `/tmp/groups-browser-postreview.log`, `/tmp/groups-webkit-investigation.log`.
- `npm ci` reported 19 dependency vulnerabilities (4 low, 13 moderate, 2 high); not investigated or changed in this batch. Tests used isolated credentials; `.env` was not copied.
- Child workspace removed. Lead retains this workspace, final integration and shared planning records. No bookmarks moved or deployment performed.
