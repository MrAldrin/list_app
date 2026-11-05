# Theme and interaction exploration

Lifecycle: tracked

## Status and outcome

Proposed design assignment. The owner requested this scope; execution and an
overnight agent run still need explicit approval. No app implementation is
approved by this plan.

Create a local HTML gallery with **20 distinct drafts: five at each of four
levels of design freedom**. Help the owner compare modest theme changes with
larger redesigns, then choose a few directions to refine. The categories are
not visual styles such as warm, retro, or minimal. They define how much the
draft may change.

Existing references: [visual-refresh feedback](visual-refresh.md),
`frontend/src/lib/ui/theme.ts`, and `frontend/src/app.css`. The earlier feedback
is context, not a requirement to repeat those mockups. Do not retire that plan
or treat its unresolved feature ideas as accepted behavior.

## Four levels, five drafts each

| Level | May change | Must stay close to the current app |
| --- | --- | --- |
| **1. Colors only** | Background, surface, text, accent, border, and state colors | Fonts, spacing, shapes, layout, labels, and control positions |
| **2. Traditional restyling** | Colors, fonts, type scale, button shapes, borders, shadows, icons, and spacing | Familiar room/list organization, actions, and control placement |
| **3. Broader redesign** | All styling plus page composition, navigation presentation, item/card layout, button placement, and visual hierarchy | Recognizable list tasks and understandable interaction; no new product feature is assumed |
| **4. Unrestricted experiment** | A different interaction concept, navigation, visual metaphor, layout, typography, image backgrounds, or presentation | A usable demonstration of the core list tasks; no production changes |

Levels 1 and 2 provide ten safer options. Levels 3 and 4 provide ten wider or
experimental options. Five drafts at one level must offer different directions,
not five tiny variations of the same palette. Level 1 must be substantially
more varied than the current similar-looking themes without changing layout.

For levels 3 and 4, adjust spacing and components to fit the direction. Do not
force a new typeface or visual metaphor into the old component dimensions.
Images, illustration, gradients, texture, terminal or retro treatments are
possible tools, not required quotas. Experimental freedom is freedom in the
prototype, not authority to change the real app or its data rules.

## Deliverable: one local HTML gallery

Use a self-contained static preview with local assets. Prefer simple HTML, CSS,
and JavaScript over a new frontend framework. Do not add an app theme selector
or twenty production themes.

The gallery must provide:

- An overview grouped by the four levels, with five clearly named drafts each.
- A current-app reference, outside the count of twenty.
- Selection of two to four drafts for larger side-by-side comparison.
- A focused phone-size preview and a room/list view switch for each draft.
- Light and dark views. Preserve the direction in each, rather than mechanically
  inverting colors. Explain any experimental concept that needs a deliberate
  adaptation between modes.
- A short note per draft: what changed, why it differs, and whether implementation
  would be palette-only, component styling, layout work, or interaction work.
- Basic working mock interactions: add an item, check/uncheck an item, and
  open/edit an item. A reload may reset the sample. No backend or persistence
  is needed. Label other nonworking controls as illustrative.

Use the same sample content and task scenarios in every direction: multiple
lists; long and short names; checked and unchecked items; quantities; tags;
and due dates. Show what happens to this information in each design. Do not
make a design look cleaner by silently omitting difficult content or actions.
Due information must remain findable even when its presentation changes.

Use synthetic data only. Keep the gallery separate from the production build,
app routes, real databases, saved preferences, and service worker.

## Research and drafting sequence

1. Inspect the current app and styling. Establish a representative reference.
2. Research a small, varied set of design references. Keep source links and
   explain the transferable idea. Create original drafts; do not copy another
   product's branding or whole interface.
3. Sketch a direction matrix: four freedom levels, five genuinely distinct
   proposals in each. Check that adjacent levels are not interchangeable.
4. Build the gallery and twenty drafts. Use reusable sample data and preview
   plumbing, but do not make levels 3 and 4 share a fixed layout that prevents
   actual redesign. Avoid twenty independent app implementations.
5. Inspect rendered previews at phone and desktop widths. Review the actual
   page, not only CSS source. Fix obvious clipping, unreadable text, and broken
   interactions.
6. Have a fresh reviewer check category boundaries, variety, usability, and
   accurate implementation labels. Refine clear problems before handoff.

## Quality checks

- All twenty drafts render, with five at each freedom level.
- Level 1 changes only colors; level 2 does not quietly rearrange the app.
  Levels 3 and 4 include genuinely different compositions or interaction ideas.
- Representative sample content remains accessible in every draft.
- Add/check/edit mock interactions work in each direction, including keyboard
  use. They must not send requests to the real app.
- Text is readable, ordinary text targets at least 4.5:1 contrast, and meaningful
  controls/focus indicators remain visible. Do not rely on color alone for state.
  Use suitably sized touch controls and avoid motion-dependent interaction.
- Long names and controls do not cause unintended horizontal scrolling at a
  phone viewport. The outer comparison gallery may scroll intentionally.
- Check light/dark behavior, image contrast, font loading, and missing assets.
  Inspect in Chromium and WebKit; report any engine limitations rather than
  claiming a full production accessibility or compatibility audit.
- The preview works without remote font/image requests. Use system fonts or
  bundled licensed fonts; use original or appropriately licensed local images.
  Record asset licenses and attribution. No paid assets or services.
- No new gallery feature should become an engineering project. Use existing
  tools for rendering, screenshots, and basic contrast checks where practical.

## Authority and limits

After execution approval, the assigned agent may create prototype files and
local assets in its own isolated jj workspace. It may research public sources
and create mock interactions. Any concurrent writers need separate workspaces.

- No changes to real app source, APIs, business rules, database schemas,
  notification behavior, or production settings.
- No app integration, deployment, pushes, bookmark moves, new app dependencies,
  paid services, external tracking, or production data.
- Radical drafts may suggest different interactions. They must identify new
  feature assumptions, not silently turn them into product requirements.
- No extra backlog items or changes to shared plans without an agreed docs-desk
  write window. Owner selection and production implementation are later tasks.
- Keep artifacts bounded. Do not launch competing heavy browser jobs while
  the test-suite task is profiling. Agree a schedule for browser rendering.
- Serve the gallery only when authorized, bound to loopback, in a visible
  Zellij pane. Use a verified free port, not another task's port or server.
  Do not open a browser tab unless asked.

## Morning handoff

Provide:

- The gallery path and a verified local URL if a server was approved.
- A compact index of the twenty drafts by level, with distinguishing features.
- A balanced shortlist: an easy-to-implement option, a substantial redesign,
  and an experimental option, with reasons. The owner makes the selection.
- Which drafts require only theme tokens versus component/layout/interaction
  changes. No precise implementation estimates without examining the seams.
- Check results, review findings, known limits, and asset/source credits.
- Change IDs, workspace ownership, artifact location, and cleanup instructions.

Do not describe any draft as an accepted app design. Preserve the gallery for
owner review; remove its workspace only after the result is preserved and the
owner is finished with it.

## Execution record

- Backlog placement: awaiting owner decision.
- Execution approval: pending.
- Task owner/session, model settings, and workspace: not assigned.
- Work window, stop time, concurrent workers, and artifact budget: not agreed.
- Preview server/port and browser-work schedule: not agreed.

## Progress

- [x] Scope twenty drafts by four levels of design freedom.
- [ ] Agree backlog placement and approve execution limits/ownership.
- [ ] Research references and establish the current-app comparison.
- [ ] Build twenty drafts and the local comparison gallery.
- [ ] Review rendered designs, run checks, and address clear issues.
- [ ] Deliver the morning handoff and await owner shortlist.
- [ ] Record refinement/implementation decisions and preserve the gallery
  before workspace cleanup or plan retirement.
