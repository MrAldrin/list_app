# Named item groups delivery

Lifecycle: temporary

## Brief (Lead-owned)

Implement Heming's authorized named item groups using `plans/named-item-groups.md` and `plans/decisions-for-heming.md`. Allow room users to create and reuse named groups on lists; one tap adds the group, skipping all existing matches including checked items. Do not uncheck existing matches. Use per-item retry-safe operations with clear partial results, concurrency-safe server checks, offline queue/reconciliation and UID remapping as in the reviewed plan. Cached groups may be used offline; management can require connection. Public-share-only access must not expose room catalog. If this cannot be implemented safely under current architecture, report blocker and options before expanding scope.

Base `mutymmln` 864b271b; integration destination default line. Owner approved integration on default but forbids moving integration/main, pushes and deployment. No unrelated work, AI or changes to security-small. Other planned features are not in this batch. Follow architecture and API compatibility/version gates; update feature docs and tests, including auth, live updates, offline replay, UID mapping, partial failures and limits. Group storage, feed/snapshot and server operations must not lose existing data. No shared backlog/plans/decisions edits: Lead owns those files.

Full frontend, Python and browser checks plus fresh independent review required; report exact results, retained artifacts, failures and limits. Owner delegated ordinary design choices; escalate genuine semantic, security, loss or scope ambiguity with recommendation. Prior full combined browser run had two failures (Firefox sign-in, WebKit offline navigation); both passed isolated; do not claim that run passed.

## Assignment

Conductor uses GPT-6.1 Terra medium; bounded children Luna xhigh, escalate Sol medium if needed. Lead owns entry workspace `/home/hsa/projects/tmp-listr-groups`, integration and cleanup; Conductor owns child workspaces. One writer per workspace. `.env` absent; tests use isolated credentials, no secrets copied. Report to Lead via intercom.

## Status (Conductor-owned)

Active. Conductor 01a190c4 owns child workspace `tmp-groups-implementation` at `/home/hsa/projects/tmp-groups-implementation`. Implementation `xxktorwz` passed independent review after fixes. Integrating into the batch workspace; combined checks remain. Lead retains entry workspace and final integration.

## Closeout (Conductor-owned)

Pending.
