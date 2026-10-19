# Svelte deploy: migration and rollback record

> Status: history. The NiceGUI code and `NICEGUI_STORAGE_SECRET` are no longer
> in `src/`, so these steps cannot run as written. Current restore steps are in the
> [deployment guide](../deployment.md#restoration-and-rollback).

## Migration

The first Svelte deploy moved the production database from version 2 to 4
(offline-ready ids and change tracking). It took the pre-migration copy first.

A rollback to a commit from before the Svelte switch has no `Dockerfile`, so it
builds with the dashboard builder setting. The NiceGUI app also needed
`NICEGUI_STORAGE_SECRET`, which was deleted from the Railway service.

## Rollback steps for the Svelte deploy (database version 2 to 4)

The old NiceGUI code refuses the version 4 database, so a rollback is two
steps, in this order:

1. Restore the pre-migration copy (`/data/list-pre-migration.db`, or the backup
   from the [deploy script](../deployment.md#backup-before-deploying)) to `DB_PATH`, as in the
   steps above. Changes made since the deploy are lost.
2. Redeploy the previous commit (the revision you noted before deploying). It
   needs `NICEGUI_STORAGE_SECRET` (set a new random value first) and builds
   with the dashboard builder setting (see [Railway settings](../deployment.md#railway-settings-to-check)).

Restoring alone leaves the new code on an old database: it would migrate again.
Redeploying alone fails at startup on the newer database.
