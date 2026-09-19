# Self-service rooms through expiring invitations

## Agreed scope
- Admin generates an unguessable invitation valid for seven days and can revoke it early.
- Invitations are reusable: anyone holding one can create their own password-protected room.
- Expiry/revocation prevents new creation; existing rooms continue working.
- Room passwords still grant room management. Global admin can see all rooms.
- No accounts, owner/member roles, CAPTCHA, rate limiting, or backup system in this step.
- Public-by-link lists retain their existing behavior.

## Implementation stack
Task prefix: `rooms - self service`. Each jj change gets its own imperative summary.
1. Record this plan.
2. Add an additive invitations schema and invitation service with tests. Store only SHA-256 hashes of random tokens; enforce expiry/revocation during the room-creation transaction.
3. Add admin invitation controls and a mobile-friendly creation page. Recheck admin authentication in callbacks. Route successful creators to the existing room password flow (no new authentication mechanism). Add UI tests and update architecture/docs.

## Verification
- Check seven-day lifetime, exact expiry boundary, invalid/revoked links, reuse, validation, and transaction rollback.
- Verify invitation possession does not authorize existing rooms; existing room/admin access tests remain green.
- Test admin-only callbacks and creation-page behavior, including links expiring after page load.
- Use SQLite's backup API to create a temporary copy of local `list.db`; initialize twice, compare all pre-existing table rows, and run integrity/foreign-key checks. Never mutate the original.
- Run required Ruff formatting/lint and full pytest checks for each Python change.
- Review diffs/stack, retain this plan, leave an empty working change. Do not move bookmarks or integrate.

## Risks and trade-offs
- A forwarded invitation permits creation until it expires or is revoked. This is intended.
- No abuse throttling initially, per the accepted small-project risk.
- The raw invitation is shown only when generated; if lost, generate another.
- Production migration occurs at startup. This change adds a table, not a rewrite of existing room/list data. No production backup automation is added.

## Progress
- [x] Plan recorded.
- [x] Invitation persistence/service and tests: 162 tests pass; Ruff clean.
- [ ] Admin and creation UI with tests and documentation.
- [x] Local-copy migration: initialized twice; all 3 rooms, 3 lists, 43 items and 1 access token unchanged. Integrity and foreign-key checks pass. Original untouched.
- [ ] Final UI checks and stack review.
