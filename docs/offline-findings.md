# Offline experiment: findings and disposition

## Outcome and evidence limits

The owner reports that repeated real-use attempts did not deliver acceptable
offline behavior and that production was rolled back to `main`. The experimental
changes remain in Jujutsu history; this is not a claim that the experiment was
removed from every branch. Production rollback is owner-reported, not independently
verified here.

The experiment added a separate read-only browser shell and local snapshots
alongside the NiceGUI online interface. Its documentation records successful
narrower desktop and Android-emulator checks, but outstanding physical-device
acceptance. Those checks did not establish a satisfactory installed-iPhone
experience. This review did not rerun the tests or establish one specific root
cause for the real-use failures.

Evidence retained at the time of this decision:

- Experiment tip: change `plxvtrsm`, commit `7873ef1b` (includes later view changes).
- Earlier checkpoint: bookmark `backup-offline-read-only`, commit `6279f6c7`.
  This bookmark is not the full experiment tip.
- Experiment-only references: `plans/offline-readonly.md`,
  `plans/offline-options.md`, `plans/iphone-installed-offline-acceptance.md`,
  and the browser/emulator testing guides at those revisions.
- Production baseline reported by the owner: `main`, commit `1a89bc71`.

These are historical revision references, not links to files expected on main.
For example, inspect them with
`jj file show -r 7873ef1b plans/offline-readonly.md`.

## Conclusions

- NiceGUI's server-driven interface makes independent offline interaction harder.
  The experiment's failure does not prove that offline web apps are unsuitable,
  nor that NiceGUI can never support a limited offline fallback.
- Web hosting is not the obstacle: a browser can run a locally cached interface
  and store data locally. A native iPhone app is not required, and simply wrapping
  the existing NiceGUI interface would not remove its server dependency.
- A browser-side frontend is the chosen future direction. Changing framework
  alone does not provide local persistence, reliable startup or synchronization.
- Offline viewing should become the first offline capability of that same
  frontend, not another throwaway fallback UI. Future editing must inform its
  data model from the start. Some evolution is expected; zero rework is not promised.
- Validate cold launch and saved data on the owner's actual iPhone early.
  Desktop and emulator passes are useful but not substitutes for that acceptance.

The staged work and unresolved choices live in the
[migration plan](../plans/offline-frontend-migration.md). The existing experiment
is retained as evidence, not scheduled for production integration.
