# Theme exploration: evidence and decisions

## Assignment and ownership

Task 3 is an unaccepted local prototype. The authoritative brief is
[theme exploration](../../plans/theme-exploration.md). Conductor session
`01a1ae1f-51f3-7754-b9c5-ae51d2bdbb75` owns execution in Lead-managed
`night-themes`. The Lead owns the entry workspace lifecycle and shared plans.
No app source, app settings, API, or production build changes are authorized.

Child workspace `night-themes-gallery`, at
`/home/hsa/projects/list_app-night-themes-gallery`, is Conductor-created and
managed. Implementation worker `35177b99` was its first writer. Read-only
reference scout `559b310c` completed without edits. Harness worker `362c77ac`
was the sole writer in Conductor-managed `night-themes-checks`, at
`/home/hsa/projects/list_app-night-themes-checks`; its boundary was
`prototypes/theme-gallery-check.cjs` only. Both first-attempt workers used
verified Luna/xhigh. Maximum active children: two. Graph changes are serialized by the
Conductor. No child may launch children or mutate bookmarks.

## Research before implementation

Public references inspected on 2026-11-06. These are ideas, not copied assets
or product requirements:

- [GOV.UK task list](https://design-system.service.gov.uk/components/task-list/):
  clear row hierarchy and explicit text states. Transfer legibility, not its
  service-completion rules.
- [Carbon structured list](https://www.carbondesignsystem.com/building-blocks/core/components/structured-list/guidelines):
  aligned metadata and strong dividers. Adapt alignment to a narrow phone.
- [Things](https://culturedcode.com/things/features/): focused task hierarchy
  and headings. Do not assume new scheduling behavior.
- [Trello cards](https://support.atlassian.com/trello/docs/add-and-customize-cards-and-lists/):
  visible card metadata and grouped spatial scanning. Do not add workflow states.

Prior owner feedback in [visual refresh](../../plans/visual-refresh.md) favors
Market's clear, colorful room cards and thumb access. It does not approve
identities, grouping rules, quantity shortcuts, or new product behavior.

## Direction matrix — fixed before implementation

Each row contains five proposals. Every proposal has light and dark adaptations.
The reference is separate from these twenty.

| Freedom | Drafts and distinct ideas | Implementation boundary |
| --- | --- | --- |
| 1: colors only | Porcelain Ink: near-neutral black/white; Citrus Grove: cream/forest; Marine Signal: pale cyan/navy; Aubergine: lavender/plum; Ember Clay: sand/rust | One exact shared reference DOM and geometry; color variables only |
| 2: traditional restyling | Market: soft round friendly cards; Editorial: serif titles and fine rules; Utility: square compact engineering; Cushion: generous pill forms; Ledger: monospaced numbers and ruled rows | Familiar header, row controls, bottom add position; component styling only |
| 3: broader redesign | Index Rail: persistent list navigation beside items; Category Atlas: tag sections; Today Ledger: due-date sections; Split Sheet: room overview plus selected list; Card Mosaic: item cards with metadata footer | Five separate compositions; grouping is display-only; no new data rules |
| 4: unrestricted | Field Notes: notebook spread; Dispatch Board: columns for existing checked/unchecked state; Focus Deck: one prominent item plus complete index; Terminal: command-styled form and numbered rows; Orbit Map: spatial room navigation with linear accessible item view | Five interaction/composition concepts; all core tasks remain button/form accessible; new navigation is prototype-only |

Palette variety cannot change level 1 geometry. Levels 3 and 4 must not merely
apply new colors to the reference template. Tags, quantities, due information,
long names, and completed entries stay available in every direction.

## Status

- Reference scout and harness author complete. Original implementation run
  `35177b99` timed out after 1,800,000 ms. Four partial gallery files remain
  preserved at `xzoyyonu/d26149f1`; JavaScript syntax now passes.
- Bounded finish retry `4d7d7e84` completed wiring and gallery notes in
  continuation `svmyqwmz`. Requested and host-reported selection: Haiku/max.
  The child reported low effort or could not confirm max. Host `status.json`
  records requested/launch model `claude-code/claude-haiku-5-5:max` and thinking
  `max`; provider-internal effort remains unconfirmed. This is a model-setting
  limitation, not an unqualified verified-max claim. Its frozen parent was not
  amended. The retry did not rebuild the twenty drafts.
- Advisory source reviewer `cc4bea4a` uses verified Luna/xhigh. Final stable
  actual-source and rendered review is still required.
- Gallery-only server started in owned floating pane 59, tab 20. After reviewed
  integration, it moved to **pane 72**, serving the entry workspace's
  `prototypes/theme-gallery/` only, bound to `127.0.0.1:8766`. Startup and HTTP
  200 were verified. Requests for `/.env` and `/docs/scope.md` returned 404.
  Old pane 59 was closed. The existing 8765 server is untouched.
- Exploratory pass 1 exited 1 in both engines before design checks: a gallery
  JavaScript syntax error prevented the overview from rendering. Evidence:
  `.night-evidence/themes/pass1/evidence.json`. Failed evidence
  is retained. Finished check pane 60 was removed; server pane 59 stayed open
  for the next pass.
- The first stale-workspace recovery exposed an empty/partial divergence in
  this task's own child change. The partial source was restored and only the
  empty task-owned revision was abandoned. No parked work was changed.
- Pass 2 exited 1 before the full matrix: a harness selector counted both
  Remove buttons and preview articles. The actual baseline room grid also
  overflowed. Both were repaired; failed evidence is retained.
- Pass 3 completed 336 engine/mode/view/viewport cases, but exited 1. It exposed
  the Index Rail phone layout, contrast defects, intentional-scroll false
  positives, and a missing reference-geometry capture in the harness. Repairs
  preserve all twenty cases and content assertions. Intentional tag/list strips
  are recorded separately; preview-root overflow is still checked.
- Pass 4 completed the full matrix. Contrast remained red, including placeholder
  and native Edit-button colors. Route, sample-content, basic keyboard actions,
  comparison, sampled focus/targets, geometry, and overflow checks passed.
  These checks did not yet assert focus retention after a DOM update.
- Parent repairs also use actual inline app icon paths, correct source checkbox,
  note, quantity, and Options dimensions, and add local Material license text.
  Final actual-source and rendered review must cover these repairs.
- Pass 5 still found native Edit-button contrast failures, especially in WebKit.
  Explicit themed button backgrounds fixed them. Pass 6 exited 0 with 1,444
  checks, but was not treated as final evidence after stronger checks were added.
- Pass 7 exercised keyboard actions in both modes and tested retained focus. It
  exposed an actual focus-restore selector defect. The selector was corrected.
  A base-style priority error that suppressed wider-draft palettes was also fixed.
- Pass 8 exited 0 with 1,572 checks. This includes 336 engine/mode/view/viewport
  cases, 84 keyboard scenarios, and comparison-column focus/unique-ID checks.
- Independent review `b0e59400` blocked handoff on a sticky toolbar overlay and
  found narrow desktop-preview layouts and overlap between two level-3 drafts.
  Parent repairs remove the sticky toolbar, use preview-container breakpoints,
  and make Split Sheet a work-first page with a separate room-inventory grid.
  Ad-hoc reference phone shrink rules were removed to retain source dimensions.
- Pass 9 exited 0 with 1,572 checks after those repairs. Supplemental dark room
  and comparison captures cover Chromium and WebKit. Comparison layout was then
  made a single intentional scrolling row, with a same-row assertion added.
- Re-review `cfb23c56` confirmed the earlier repairs, then found two narrow
  content issues. Index Rail now uses the selected list's tags. Today Ledger
  sorts a copy by due date, with undated items last. Re-review `11fe1018` found
  no remaining issues after inspecting actual source, the strengthened harness,
  and new Chromium/WebKit dark captures, including four-way comparison.
- Final combined-entry run passed with observed process exit **0**: **1,828
  checks**, **336** engine/mode/view/viewport cases, **84** keyboard scenarios,
  and **252** secondary-list cases. It includes date-order, exact selected-list
  tags, focus retention, unique IDs, and same-row 2–4 comparison checks. There
  were zero failures, external requests, page errors, or console errors.
- `node --check` passed for gallery JavaScript and the harness (exit 0 each).
  The seven delivered source files match the captured SHA-256 manifest. After
  integration, directory/file comparisons against the children found no lost
  repairs. No app/Python regression suite was run: no app or Python source
  changed in this task.
- Compact tracked results are in [the check summary](theme-exploration-checks.json).
  Full runs and reviews remain under `.night-evidence/themes/` (ignored), about
  141 MiB before final closeout. All failed runs are retained; no large rendered
  evidence was deleted. Preserve this directory before entry-workspace cleanup.
- Independent combined-entry review `e14b5e81` inspected the integrated source,
  harness, combined phone/desktop renders, and results. Verdict: **OK, no issues
  found**. It confirmed all known repairs survived composition. Reviewer model
  and reasoning were verified as Luna/xhigh.

## Shortlist for owner review

These are recommendations, not design selections or accepted app requirements.

- **Easy — Citrus Grove:** a clear warm/forest palette with unchanged reference
  geometry. Its production seam is the color-token map. Porcelain Ink offers a
  quieter neutral alternative.
- **Substantial — Card Mosaic:** metadata stays visible on item cards. This needs
  item component and layout work, but no new grouping rule. Category Atlas is
  another strong comparison, with display-only tag grouping still unaccepted.
- **Experimental — Orbit Map:** original spatial room navigation leads into a
  linear item list. It needs navigation and layout work; the map is a prototype
  assumption, not a product commitment.
- **Familiar styling alternative — Market:** keeps control placement while adding
  softer components. It connects to prior owner feedback without claiming that
  feedback selected this draft.

## Limits to carry into handoff

- Static synthetic prototype only. No real APIs, storage, app dependencies,
  service-worker behavior, app integration, acceptance, or deployment.
- The reference covers one configured main room/list state: quantity controls
  off and only an item's own tags shown. Menus, due-center panels, search
  suggestions, and list rename/delete are clearly illustrative. The local edit
  dialog is a working mock, not a full app-dialog reproduction.
- Level-1 geometry is checked against this source-derived static reference.
  This is not evidence of pixel parity for every state of the real app.
- Contrast sampling, DOM checks, and rendered review are bounded prototype
  checks, not a production accessibility or compatibility audit. The browser
  harness records unsupported/gradient text cases rather than certifying them.
  Checks used the existing Linux headless Playwright engines, not real Safari
  or a physical device. Packaged engine versions are recorded in the summary.
- The synthetic clock is fixed at 6 November 2026; due labels demonstrate that
  sample day. They are not real reminders.
- Fonts are local system stacks. Main reference icons use the existing app's
  Material paths with credits and bundled Apache 2.0 text. No remote font/image
  loading, paid assets, tracking, or real data is used.

## Final handoff

**Complete as a local prototype; not accepted app work.** No owner design
selection, production implementation, bookmark movement, or deployment occurred.
The Lead owns shared-plan status and the result bookmark.

- Gallery: `prototypes/theme-gallery/preview.html`.
- Verified URL: <http://localhost:8766/preview.html>.
- The matrix above indexes all twenty drafts. Each gallery card also carries its
  freedom level, distinguishing idea, and implementation seam.
- Final checks and review are complete. The gallery and harness source hashes
  match the final check summary. No gallery or harness source changed after
  the combined run.
- All bounded children are finished. Conductor-created workspaces
  `night-themes-gallery` and `night-themes-checks` were forgotten and removed
  after reachability, identical-file, artifact, and process checks. No child cwd
  remained in use. No pre-existing or Lead-managed workspace was removed.
- The Lead-managed entry remains at `/home/hsa/projects/list_app-night-themes`.
  The conversation stays interactive. The Conductor retains ownership of
  gallery server pane **72**, tab **20**, until an explicit transfer or stop.
  Keep it for owner inspection. Before entry cleanup, stop that server and
  preserve `.night-evidence/themes/` (about **141 MiB**) in a usable location.
  The gallery itself is tracked and does not depend on the removed children.
- Check-job panes and old server pane 59 are closed. The existing docs server
  and all unrelated panes remain untouched. No production service was started.

Ordered task change IDs (oldest first):

1. `runkwvoytwuolxvokltynprzupluwmzv` — matrix and research.
2. `ksptlxsrvtrzkqpnsnspqswnxvluoxvp` — first exploratory failure.
3. `uxvwlmvsvkskmkzxpkxnonqplklquvsn` — iteration evidence and review findings.
4. `xzoyyonuqtuzlxqoklnkzzoxxyupywpu` — twenty-draft implementation.
5. `svmyqwmzspxyywuvtuzuyqkolluwvpuv` — reviewed layout, focus, and contrast repairs.
6. `wonlzylosyuyzslmxvxspyysrlpzrpmp` — browser/content/interaction harness.
7. `yuqlozromxutplkkpvmzpkzvspvqssnn` — combined verification and closeout.

The final working copy is left as an empty child. Graph mutation control returns
to the Lead after the closeout message. Outstanding owner decision: choose
which directions, if any, to refine. The shortlist is advice only.
