# Deploy backup: stream over ssh

Lifecycle: temporary

Change [`scripts/deploy_backup.py`](../scripts/deploy_backup.py) so the
production backup travels over `railway ssh` straight to this machine. Today it
is written to the volume, downloaded, and then must be deleted by hand, because
Railway refuses `volume files delete` from scripts.

## Decisions

- **Temp folder, not the volume.** The remote side makes the backup-API copy
  in a fresh temp folder in the container (`/tmp`, which is not the volume) and
  checks it there. The folder is always removed, even on failure.
- **Text-safe transfer.** `railway ssh` output is meant for a terminal, so the
  remote side sends the file as base64 text between start and end marker lines.
  The local side drops any `\r`, decodes, and writes the file. Base64 roughly
  adds a third to the size (~150 KB today), which is fine.
- **Same checks as before.** The remote side prints size and SHA-256 first.
  Locally the script checks size, SHA-256, `integrity_check` and
  `foreign_key_check` before anything else runs. A copy that fails is kept as
  `*.db.unverified`.
- **Wake first.** Before ssh, the script requests the app's home page with
  `curl` (up to 90 seconds). A sleeping Railway app starts on the first web
  request. The URL is a constant in the script.
- **Clear stop when ssh misses the container.** If the output has no result
  line, the script stops. When the output looks like Railway's account-service
  reply, the message says ssh did not reach the container and to rerun in a
  minute.
- **Still check the target.** `railway volume list --json` stays as the guard
  that the linked environment is `production` with one `/data` volume. Volume
  download and delete are removed.
- **Not tested against production by the agent.** A read-only transfer test
  over `railway ssh` was blocked, so the owner's first `--backup-only` run is
  the real test. The checksum catches any damage in transit.

## Steps

1. **Script:** wake step; remote code writes to a temp folder and streams
   base64; local decode, write (`0600`, never overwrite) and verify; clearer
   "did not reach the container" stop; remove volume download and delete.
2. **Tests:** update the fake runner; run the real remote shell code locally
   and decode its output; cover wake order, `\r` handling, missing markers,
   the account-service reply, and the failed-wake stop.
3. **Docs and backlog:** update
   [backup before deploying](../docs/deployment.md#backup-before-deploying);
   replace the backlog item with a manual check for the first real run.
4. **First real run (owner):** `uv run python scripts/deploy_backup.py
   --backup-only`. Expect "Backup verified" and no new file on the volume.

## Progress

- [ ] 1. Script
- [ ] 2. Tests
- [ ] 3. Docs and backlog
- [ ] 4. First real run (owner)
