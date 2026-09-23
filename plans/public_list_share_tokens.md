# Plan: Secure Public List Share Tokens

Created: 2026-09-14
Implemented: 2026-09-23. Production/manual verification remains pending.

## Outcome

Implemented the approved separate-token design: `/share/{token}`, 256-bit random
values, migration/backfill, public view/edit, and room-authorized token rotation.
Old slug URLs require room access and never publicly disclose new tokens.

Room navigation deliberately retains authorized `/list/{slug}` URLs rather than
using public tokens: room tabs remain independent of public-link rotation.
Share buttons use the canonical public route. No stack or remembered-access
changes were needed.

Current behavior, security boundaries, implementation details, and rollout checks
now live in [docs/public-sharing.md](../docs/public-sharing.md). This plan is
retained for outstanding manual verification; it is not proof of deployment.

## Progress tracking

- [x] Choose `/share/{token}` as the canonical public route
- [x] Add token schema, backfill, generation, and lookup
- [x] Update sharing; retain room-authorized internal navigation
- [x] Add room-authorized reset with confirmation
- [x] Restrict legacy slug URLs
- [x] Revalidate open public pages and reject revoked-token writes/undo
- [x] Add automated migration, authorization, page, and mutation coverage
- [x] Verify: 286 tests passed; Ruff formatting/lint clean. Existing Starlette/httpx deprecation warning remains.
- [x] Update current architecture and operational references
- [ ] Perform the [manual rollout and device checks](../docs/public-sharing.md#rollout-and-verification)
