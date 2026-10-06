# Small-fixes deployment: 2026-10-06

Current procedure: [deployment guide](../deployment.md).
Remaining production and device checks: [backlog](../../plans/backlog.md#manual-checks).

## Shipped

- Revision `b7c411bc359e9345bc4e326f6fbba25d5c9608d5`.
- Previous production revision: `7538ef86f247bcf5220d0f0e6954958425a22835`.
- URL-only native sharing, room-menu dark mode, positive hide-done counters.
- Railway deployment `e61e59de-3168-4be1-87d1-319d22221a0c`: SUCCESS.

## Verified

- Production configuration: app password present, `/data/list.db`, volume at
  `/data`, one replica, no custom build/start command.
- Verified local backup before rehearsal and fresh backup before pushing.
  Final pre-deploy copy:
  `~/.local/share/list_app/backups/list-deploy-20261006T142735Z-8c1def4b.db`.
  Older backups were retained.
- Isolated startup against a private copy of production: migration 4 to 5;
  item rows, list identities, share tokens and counts preserved; zero-count
  settings converted as intended; integrity and foreign keys clean.
- Local checks: 296 frontend tests, Svelte checks, frontend lint, Ruff,
  1203 Python tests and all 168 browser tests passed.
- Pushed through `scripts/deploy_backup.py` with the owner's deployment approval.
- Railway used the Dockerfile; startup logged migration 4 to 5 with no error
  in the inspected startup log.
- Production read-only checks: schema 5, integrity OK, no foreign-key
  violations, no out-of-range counters; room/list/item counts and a hash of
  list identities/share tokens match the final pre-deploy backup.
- HTTPS start page returned 200.

## Not verified here

Authenticated production workflows, live updates across two browsers,
restart persistence, password-reset revocation, real iPhone Copy, room-menu
interaction and home-screen behavior remain manual checks. Local browser
coverage is not production or real-device evidence.

## Operational note

Railway CLI warns that `railway.json` remains supported until 2026-12-01,
then recommends infrastructure as code. No deployment configuration was changed.
