# Offline editing release validation

Current behaviour: [Offline use](../offline-viewing.md).
Approved scope and decisions: [offline editing details](offline-editing-details.md#decisions).
Deployment procedure: [Deployment checklist](../deployment.md#deployment-checklist).

## Candidate

Implementation change `qpptpsss` (`9c5f361d`), based on the live fixes at
`f5692822`. No production or integration bookmarks were moved or pushed.

## Automated evidence

- Final candidate: `uv run pytest browser_tests -q -n 4`: 315 passed.
  Includes a real build swap with a stored waiting change.
- Final repair: 538 frontend tests and 45 affected browser tests passed;
  frontend lint, type checks and build passed.
- Before the final TypeScript-only repair: 1,285 Python tests passed;
  Ruff formatting, lint and ty passed. No Python changes followed those checks.
- Independent review found two rejection-lifecycle bugs: cross-tab entry loss
  and a stuck retry after sign-out. Both were fixed with regressions.
  Targeted independent re-review found no remaining issues in those fixes.
- Rehearsed database migrations 6 to 8 on an isolated copy of an existing
  local production backup. Integrity and foreign-key checks passed, and room,
  list and item counts were preserved. The source backup was not modified.

## Release boundary

The owner waived pre-release manual testing. Real iPhone and installed-app
behaviour is not verified by this waiver or desktop browser automation.

Deployment still requires explicit approval, a fresh backup through the deploy
script, and the remaining operational checklist. The existing local-backup
rehearsal is not a fresh production backup. Schema rollback requires a matching
database backup; rolling back code alone is not sufficient.
