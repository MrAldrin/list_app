# Railway Config Removal Plan

Lifecycle: temporary

Goal: keep Railway building the root `Dockerfile` after 2026-12-01, when
Railway stops reading `railway.json` (Config as Code).

## Decision

Delete `railway.json` and rely on Railway's Dockerfile detection. Railway uses
a file named `Dockerfile` at the source root and logs
`Using detected Dockerfile!` in the build. See
[Railway's Dockerfile docs](https://docs.railway.com/builds/dockerfiles).

Not chosen now: Railway Infrastructure as Code (`.railway/railway.ts`) or
Alchemy. Railway IaC is not applied on push; you apply it with the CLI. Both add
a new tool and workflow for one setting. Alchemy stays an idea in the
[backlog](backlog.md#ideas).

Why before the deadline: while `railway.json` is still read, a failed build can
be fixed by restoring the file. After 2026-12-01 that fallback is gone.

## Steps

1. Repository: delete `railway.json` and update
   [deployment](../docs/deployment.md#production-image).
2. Owner, Railway dashboard (read only): note the service's builder setting and
   the "Config file path" setting. If a path is set, clear it.
3. Owner: optional preview, changes nothing:
   `railway config migrate`. It should only show the Dockerfile builder.
4. Deploy through the normal [deployment checklist](../docs/deployment.md#deployment-checklist),
   with approval to push `main`.
5. Check the build log shows `Using detected Dockerfile!` and the `npm ci`
   step. Then run the after-deploy checks.
6. If the log shows Railpack instead: set the builder to Dockerfile in the
   dashboard and redeploy. For a quick undo, restore `railway.json` (works until
   2026-12-01).

Rollback note: a builder set to Dockerfile in the dashboard breaks a redeploy of
a commit from before the Svelte switch (it has no `Dockerfile`). Only change the
dashboard builder if step 6 needs it.

## Progress

- [x] 1. Repository change (`railway.json` deleted, docs updated; image built and served locally with podman)
- [x] 2. Dashboard settings noted (config file path: none set; builder shows Dockerfile from `railway.json`, dashboard value hidden until the file is gone)
- [ ] 3. Migrate preview (optional)
- [ ] 4. Deployed to production
- [ ] 5. Build log and after-deploy checks verified
