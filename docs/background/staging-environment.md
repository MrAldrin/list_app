# Staging environment (not planned)

A record of the staging design, kept for its reasoning. It was retired as a
plan on 2026-10-19. We push straight to production and fix forward; see the
[risk level](../scope.md#risk-level). The `staging` bookmark below is not in
use and would need a change to the [bookmark rules](../../AGENTS.md#jujutsu-development-baseline).

Goal it served: test a change on a real phone against a real Railway deployment
before it reaches production.

## Decisions so far

- **Do not create a second Railway account.** Railway's terms do not allow
  extra accounts made for more free usage, which risks both accounts, including
  production. Two accounts also mean duplicated settings and secrets.
- **Use one Railway project with two environments:** `production` and
  `staging`. Each has its own URL, variables and volume/database.
- **Branch mapping:**
  - `main` → production (as today)
  - `staging` → staging
- **Start when** paying for Railway, or sooner if the free allowance covers a
  second environment. Check current plan limits on the Railway dashboard first.

## Workflow as designed

1. Move the `staging` bookmark to the change and push it:
   `jj bookmark set staging -r <rev>` then `jj git push --bookmark staging`.
2. Wait for Railway to deploy staging.
3. Test on a phone at the staging URL.
4. If it works, move `main` to the same commit and push, following the
   [deployment checklist](../deployment.md#deployment-checklist).
   Production then runs exactly the code that was tested.

## Setup steps (if revived)

- [ ] Check Railway pricing and usage limits for a second environment.
- [ ] In Railway, create a `staging` environment in the existing project.
- [ ] Give staging its own secrets (different from production) and its own
      volume with an absolute `DB_PATH`.
- [ ] Set staging to deploy from the `staging` branch.
- [ ] Use test data only; never copy production data without a separate
      decision.
- [ ] Do a first staging deploy and phone test.
- [ ] Update [`docs/deployment.md`](../deployment.md) with the staging
      workflow once it is verified.

## Open questions

- Keep staging running, or turn it off between tests to save usage?
- Should staging data reset on each deploy or persist?

## Progress

- 2026-09-28: Plan written. Local Wi-Fi testing chosen as the free option for now.
- 2026-09-28: Phone testing over Tailscale verified; home Wi-Fi rule removed.
