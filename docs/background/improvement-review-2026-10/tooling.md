# Tooling report (saved by orchestrator from agent message)
- pytest 1360 passed in 39s (-n 8), 98% coverage of src/; vitest 593 in 7s; ruff/ty clean.
1. [H,S] Test gate in scripts/deploy_backup.py before push (ruff, ty, pytest, frontend lint/check/vitest; --browser flag optional). Script runs no tests today; jj has no hooks.
2. [M,S-M] Minimal GitHub Actions CI; needs `!.github/` in .gitignore (line 1 `.*/` ignores it). Railway deploys on push regardless unless "Wait for CI" enabled.
3. [M,S] Split docs/deployment.md (283 lines; Svelte rollback history to background).
4. [M,S,high risk if wrong] Renovate/Dependabot must target `integration`, never main (a merged PR = deploy without backup).
5. [M,S] GET /healthz with SELECT 1 + Railway healthcheck path. Sentry low value.
6. [M,S] Coverage gaps: main.py parse_port/run 59%; migrations.py backup failure cleanup lines 53-57, 31, 110.
7. [M,S-M] 106 ResourceWarnings "unclosed database": database_setup.py 140,222,345,454,565; migrations.py:25.
8. [L,S] Rate-limit tests ~16s CPU from real bcrypt; test SignInLimiter directly with clock.
9. [M,M] Browser suite redundancy: ~27 offline tests over 5 files; ~20 old-URL/compat tests retire with /sw.js kill switch (2027-04-06).
10. [M,S-M] 14 wait_for_timeout fixed waits (worst test_svelte_offline.py:328 2s) -> settled-state signals.
11. Pre-commit hooks: not useful with jj.
12. scripts/: deploy_backup.py fine; generate_app_icons.py maybe unused; ty checks src/ only.
13. Stale test numbers: docs/background/test-suite-speed.md says 192 tests/6s; plan says ~9s.
Top 3: test gate in deploy script; CI + .gitignore fix; split deployment.md.
