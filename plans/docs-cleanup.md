# Docs cleanup: short top-level docs, detail in `docs/background/`

## Goal

Top-level docs are short, current, and high quality. Long agent-written
material (investigations, evidence, measurements, audit logs) lives in
`docs/background/`. The rules are in
[`AGENTS.md`](../AGENTS.md#quality-rules-for-top-level-docs).

The owner mostly works through agents, so this is not about hiding material
from humans. Short current docs cost agents less context and stop old caveats
being read as current rules.

## Decisions

- Subfolder name: `docs/background/`. It describes the content (why, evidence,
  history), not the reader.
- `ARCHITECTURE.md`, `README.md`, and `AGENTS.md` stay at the repository root.
- One fact, one place. A top-level doc states current behavior and links to
  background for the reasoning. Background never restates current rules.
- Move, don't delete. Detail cut from a top-level doc goes to background unless
  it is obsolete or duplicated elsewhere; call out anything dropped in review.
- One doc per jj change so each rewrite can be reviewed on its own.
- No behavior or code changes. Only docs and links.

## Inventory

| File | Lines | Action |
|---|---|---|
| `docs/offline-findings.md` | 50 | Move to background as is |
| `docs/test-speed.md` | 25 | Move to background; README already states the decision |
| `docs/deployment.md` | 212 | Rewrite short; evidence and history to background |
| `docs/home-screen-installation.md` | 168 | Rewrite short; detail to background |
| `docs/browser-testing.md` | 159 | Rewrite short; measurements to background |
| `docs/item-writes.md` | 130 | Rewrite short; audit detail to background |
| `docs/android-emulator-testing.md` | 73 | Check against rules; likely light edit |
| `docs/local-network-testing.md` | 63 | Check against rules; likely light edit |
| `docs/public-sharing.md` | 61 | Check against rules; likely light edit |
| `docs/room-invitations.md` | 34 | Check against rules |
| `docs/checked-item-visibility.md` | 18 | Check against rules |
| `docs/allium/` | – | Out of scope (separate pilot) |
| `plans/test-suite-speed.md` | 415 | Keep open tasks in plan; move measurements to background |
| `plans/backup-options.md` | 173 | Keep open tasks in plan; move research to background |
| `plans/write-atomicity-audit.md` | 76 | Keep open tasks in plan; move evidence to background |
| `README.md`, `ARCHITECTURE.md` | 128, 99 | Check against rules last |

Open plans with unresolved work stay in `plans/` (see `AGENTS.md`). Only their
evidence moves.

## Steps

1. Add the quality rules to `AGENTS.md` and write this plan.
2. Create `docs/background/`; move `offline-findings.md` and `test-speed.md`;
   update links.
3. Rewrite `docs/deployment.md`.
4. Rewrite `docs/home-screen-installation.md`.
5. Rewrite `docs/browser-testing.md`.
6. Rewrite `docs/item-writes.md`.
7. Light pass on the remaining top-level docs in the inventory.
8. Split evidence out of `plans/test-suite-speed.md`,
   `plans/backup-options.md`, and `plans/write-atomicity-audit.md`.
9. Check `README.md` and `ARCHITECTURE.md` against the rules; update the README
   documentation list.
10. Final check: no broken relative links or anchors; nothing important
    dropped; backlog links still resolve.

For each rewrite: read incoming links first, keep anchors other docs rely on
(or update the links), and summarize for the owner what moved and what was
dropped.

## Progress

- [x] Step 1: quality rules added to `AGENTS.md`; plan written.
- [x] Step 2: created `docs/background/`; moved `offline-findings.md` and `test-speed.md`.
- [x] Step 3: `deployment.md` 212 → ~170 lines. Runbook code kept; pending-status text moved to backlog links. No background file needed.
- [x] Step 4: `home-screen-installation.md` 168 → 86 lines; design, implementation and past results in `background/home-screen-installation.md`.
- [x] Step 5: `browser-testing.md` 159 → ~85 lines; scenarios, design choices and timings in `background/browser-testing.md`. Added missing theme coverage.
- [x] Step 6: `item-writes.md` 130 → 50 lines, as a rules + per-action table; implementation notes and test scope in `background/item-writes.md`. Test file references corrected.
- [x] Step 7: light pass: removed status/evidence text from 5 docs; Android test details and results moved to `background/android-emulator-testing.md`.
- [x] Step 8: evidence split out of the 3 open plans into `background/test-suite-speed.md`, `background/backup-research.md` and `background/write-atomicity-findings.md`. Open tasks stay in the plans.
- [ ] Step 9: `README.md` and `ARCHITECTURE.md`
- [ ] Step 10: final link check
