# Documentation style and fidelity review

Review dates: 2026-11-05–06. Complete. Final independent audit passed after the
combined privacy restoration.

## Outcome and scope

The [assignment](../../plans/documentation-ste100.md) defines the scope. The
[run record](night-run.md) defines approval and execution limits.
This report is evidence, not new implementation or deployment authority.

The pass covers all 476 baseline tracked paths. It rewrote 52 files: 41
Markdown pages and 11 source/config files. No prose path is deferred or blocked.
The [inventory](documentation-ste100-inventory.tsv) records every path, audience,
authority, owner, protected content, disposition, writer, reviewer, and evidence.

| Final disposition | Paths |
| --- | ---: |
| Rewritten | 52 |
| Already suitable | 285 |
| Protected or partly protected; retained | 79 |
| Excluded or no explanatory prose | 60 |
| **Total** | **476** |

The baseline contains 90 Markdown/Allium pages, 327 source-comment candidates,
and 59 initially excluded paths. All 90 pages received full independent prose
inspection. Writers inspected the actual explanatory prose in 373 source/config
files, including all 327 candidates and 46 initially excluded files. The other
13 paths are empty, configuration-only, binary assets, or generated dependency
data. Seven of those received full text inspection; six are protected assets or
generated data, not prose-rewrite targets.

All rewritten files received independent original-versus-candidate review.
Independent review of unchanged Python, frontend, and test comments was sampled,
not a second full source sweep. The unchanged Android test received full
independent review. Marker counts are discovery data, not semantic-review proof.
The new report and inventory passed a separate final audit (`1b4723e1`,
`4ed40b68`). The initial BLOCK and the passing re-review are retained.

## Style sources and terminology

The official [STE overview](https://www.asd-ste100.org/about_STE.html) and
[Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) were read.
Web fetch tools returned HTTP 403; direct `curl` downloads worked. The review used
sections 1, 4, 5, and 6 for terms, sentences, procedures, and descriptions.
This is STE100-style writing, not a formal compliance or full dictionary audit.

Terms follow the [architecture](../../ARCHITECTURE.md) and current guides:
**ListR**, **room**, **list**, **item**, **checked item**, **row version**, and
**change cursor**. A public list link grants access to one list, not room
management. UI labels, API names, and necessary technical terms stay unchanged.

The edits split long sentences, state conditions directly, and remove repeated
explanations. They do not turn recommendations into requirements or historical
findings into current instructions. Examples:

| Before | After |
| --- | --- |
| Admin sign-in is not room access. | Admin sign-in does not grant room access. |
| Unsaved edits stay in the open dialog; they are never put in the shared offline queue. | Unsaved edits stay in the open dialog. They never enter the shared offline queue. |
| Production rollback is owner-reported, not independently verified here. | The production rollback is owner-reported; it was not independently verified here. |

## Batches and independent review

Every writer and reviewer used the owner's requested `openai/gpt-6-luna` with
`xhigh` reasoning. Effective launch status, environment values, or session
model/effort metadata verified the selection. No model was substituted. See
[model-selection evidence](documentation-ste100-evidence/model-selection-evidence.json).
The maximum was four concurrent bounded agents, with separate editing workspaces
and one released shared-desk writer.

Short run IDs below identify the retained full reports in
[`documentation-ste100-evidence/`](documentation-ste100-evidence/). The inventory
maps each path to its exact evidence filenames. Re-review IDs follow the first
independent review where a correction was required.

| Batch | Writer | Independent review | Result |
| --- | --- | --- | --- |
| Calibration: 3 pages | `0e8a592e` | `0a969acf`, `d877c2f6` | 3 rewritten; pass after a conditional-failure repair. |
| Root/instructions/Allium: 9 pages | `39f1c299` | `7510b309`, `91475e19` | 4 rewritten; all 9 pass. |
| Current guides/API: 12 pages | `f2ac30ce` | `d7dd3191`, `2c719a8c`, `41e96ee6` | 12 rewritten; all pass after quote, paragraph, and privacy-condition repairs. |
| Operational/API: 9 pages | `65adbd00` | `1504d9b2`, `943be276` | 5 rewritten; all 9 pass. |
| Historical H1: 15 pages | `3d375405` | `699062e0`, `fc6750d3` | 8 rewritten; all 15 pass. |
| Historical H2: 18 pages | `e9df2c25` | `a79501c7`, `1112c960` | 2 rewritten; all 18 pass. |
| Shared proposals: 6 pages | `9fceaf9d` | `e95b8ed8`, `8fe8258d` | 5 rewritten; all 6 pass. |
| Shared execution/future plans: 15 pages | `99596ee8` | `f216f161` | 2 rewritten; all 15 pass. |
| Active desk plans: 3 pages | Conductor, read-only | `fd028445` | Suitable/protected; full current-prose review; no edits. |
| Python source/scripts: 51 files | `3140887a` | `f760149a` | 2 rewritten; both pass; unchanged coverage sampled. |
| Frontend/config: 204 files | `2e873425` | `e859ab38` | 3 rewritten; all 3 pass; unchanged coverage sampled. |
| Tests/browser tests: 117 files | `35703a24` | `2ee6f89c`, `5bc50b0e` | 6 rewritten; all 6 pass; unchanged coverage sampled. |
| Android test: 1 file | `e1534645` | `d0ee1e41` | Unchanged and suitable; full independent review passes. |

The Conductor inspected the actual diffs, including complete high-risk
instruction, API, privacy, deployment, and shared-plan changes. The active
execution contract stayed frozen during the work.

### Fidelity corrections

- A historical startup failure needed an explicit counterfactual; it was not an
  observed failure. Calibration review required the repair before larger batches.
- Proposal edits restored explicit token scoping and three recommendation
  qualifiers. The Lead inspected and committed the shared result.
- The first root review incorrectly said the baseline-repair clause was already
  restored. The Conductor restored the explicit repair-before-work requirement;
  the reviewer reread all nine pages and corrected its report.
- The Conductor restored the general privacy guarantee “Nothing here is shared”
  in the reminders API introduction. Final audit found that the reviewed child
  repair was missing from the combined candidate: the parent squash had not
  captured that working-copy edit. The Conductor restored it in the entry and
  checked the other reviewed repairs. Named-channel exclusions do not replace
  the general guarantee.
- Exact quoted terms were restored: `stale`, `Waited`, and `hide after N days`.
  Historical edits also removed an invented actor and an implied observation of
  multiple users.
- Test review rejected an immediate row-chip claim. The revised comment refers
  to dialog chips, which the test checks immediately; row checks follow Cancel.
- Final Conductor inspection made the public-sharing privacy condition explicit:
  the room-name exclusion applies to browsers without valid access to that room.

Frozen reminder briefs, master staging holds, owner decisions, archive/history
protections, future assignments, and task 1's partial/BLOCK state were retained.
No historical approval became authority to resume S3, S4, or S5. The three active
desk plans remain under Lead ownership for administrative status updates.

## Verification

| Check | Result |
| --- | --- |
| `uv sync --frozen` | Exit 0; existing locked dependencies only. |
| `npm --prefix frontend ci` | Exit 0; no manifest or lockfile change. |
| `uv run ruff format .` | Exit 0; no formatting changes. |
| `uv run ruff check --fix .` | Exit 0; no fixes required. |
| `uv run pytest -q` | Exit 0; 1792 passed. |
| `uv run ruff format --check .` | Exit 0. |
| `uv run ruff check .` | Exit 0. |
| `uv run ty check` | Exit 0. |
| `npm --prefix frontend run lint` | Exit 0; Prettier and ESLint pass. |
| `npm --prefix frontend run check` | Exit 0; no errors or warnings. |
| `npm --prefix frontend run test -- --maxWorkers=2` | Exit 0; 1115 tests in 54 files pass. |
| `npm --prefix frontend run build` | Exit 0. |
| `uv run python scripts/build_docs_site.py` | Exit 0; 51 existing warnings, 39 redirects, 2810 local links. |

The language gates ran on source tip `ontwsnzu` / `5d59817d`. All 386 baseline
non-Markdown/Allium files remain byte-identical after the shared-plan merge.
The gate results therefore apply to the same source bytes in the combined
candidate; only reviewed Markdown and reporting evidence changed afterward.
See [source-reuse proof](documentation-ste100-evidence/quality-gate-source-reuse.json).

Parent checks also establish:

- Identical executable ASTs and protected directives for all 169 tracked Python
  files after removing only leading module/class/function docstrings.
- Identical JavaScript tokens, Svelte code, and TOML data in the three changed
  frontend/config files after excluding explanatory comments.
- Protected-content checks for 87 markup paths. The only occurrence-count
  difference is removal of duplicate Part 1/2/3 labels when a repeated reading
  guide was consolidated. Independent review and the Lead accepted that change;
  no quantitative value changed. The three active plans had full read-only review.
- The Allium file is byte-identical, including every formal statement.
- Baseline byte comparison finds 52 style-rewritten paths plus the Lead's
  separate run-limit amendment in `plans/night-run.md`; no other baseline path
  changed. No executable statement or configuration value changed.

Five original exports with bracketed route paths were initially empty because
jj treated brackets as a fileset pattern. Exact Git reads repaired them; all five
candidates were byte-verified unchanged. A multiline-inline-code scanner false
alarm was also corrected. Raw findings and later dispositions are both retained.

### Build and link limits

The initial task-tree build passed with 51 `page does not exist` warnings,
38 fragment-free redirects, and 2809 generated local links. The final combined
build passed with the same 51 warnings per source file. It validated 39 redirects
and 2810 links after the last privacy clarification. This is not warning-free.
The extra redirect is the new excluded report's placeholder. It contains only
the preview-exclusion notice, not report text.

The source check validates local paths and fragments against GitHub-style and
Python-Markdown heading profiles. A fragment must match at least one; this is
not a cross-renderer portability claim. Four existing fragments depend on the
renderer: two master-plan evidence links use GitHub-style double hyphens; two
speed-plan links use Python-Markdown single hyphens. These links and their
headings were retained. Generated-site anchors are checked separately by the
build wrapper. External URLs were preserved, not checked for network availability.

The Lead's separate accepted-desk build reported 47 issues, 36 redirects, and
2761 local links. That is a different content tree, not an improvement against
this task's baseline. Dependency installation reported 16 npm vulnerabilities
(4 low, 10 moderate, 2 high). No audit fixes were attempted.

## Source contradictions retained

- `docs/api-reminders.md` describes settings entry points as available;
  `docs/due-date-reminders.md` says they are hidden until phone notifications
  are ready. This task neither resolved the difference nor reactivated settings.
- `docs/room-invitations.md` retains references to “both apps.” The current
  architecture specifies the Svelte frontend. This possible stale wording needs
  a separate factual review; it was not silently corrected in a style pass.

Task 1 remains partial at `oqpnzkyx` / `570b4f8a`. Its full browser gate is red.
This task did not rerun the browser matrix or repair product behavior. Green
Python/frontend gates are not a claim of full browser acceptance.

## Changes, recovery, and cleanup

Conductor: `01a1adbe-bbbd-70a3-9663-4eb1ce3c8a22`, Sol/low. Entry:
`/home/hsa/projects/list_app-night-docs`, Lead-managed `night-docs`.

Initial baseline: `rqpqlluy` / `affacd8e`. All 476 original files also match the
reachable snapshot `rqpqlluy` / `61b52dfb`; recovery does not require temporary
exports or child workspaces. The ordered change record and byte/AST checks are
retained in the evidence directory.

| Content change | Change / commit |
| --- | --- |
| Calibration | `rrtvwtll` / `f78ffe99` |
| First shared-plan batch, Lead-owned | `nppyqqox` / `36ab5f82` |
| Python source prose | `rzxzvmxw` / `a3f945ec` |
| Root/instruction guides | `mylzwozy` / `f020dd88` |
| Frontend/config comments | `xpmslmtl` / `8f487d7c` |
| Current guides/API | `zuykpuro` / `3ae8680d` |
| Historical H1 | `wtvmntpr` / `6f9610f2` |
| Historical H2 | `tzltuvok` / `8be5534b` |
| Operational/API guides | `tpppttwv` / `e9d4b06b` |
| Test comments/docstrings | `ontwsnzu` / `5d59817d` |
| Second shared-plan batch, Lead-owned | `vmwpypkx` / `d9c4ac8f` |
| Final composition, privacy clarification, and report | `nkrslvrx`; final commit hash is in the Lead handoff |

The task line joined the accepted shared-plan changes without rewriting task 1.
Ten task-created child workspaces were removed: calibration, Python, root guides,
current guides, frontend, H1, H2, operations, test prose, and Android prose.
The Lead-managed entry and successful peer session stay open. Its `.venv`,
`frontend/node_modules`, generated site, and ignored scratch logs remain in the
entry; useful results are also retained as tracked evidence. Follow the
[workspace setup](../../README.md#new-jj-workspace) before manual app use if
`.env` is absent.

All five owned validation job panes are closed. The final independent audit
passed in `4ed40b68`; its [re-review](documentation-ste100-evidence/final-delivery-rereview.txt)
confirms that the combined privacy correction resolves the initial BLOCK.
The Lead handoff records clean empty `@` verification and graph-authority
transfer. The Lead owns result-bookmark and entry lifecycle decisions. No push,
deployment, publishing, dependency addition, or production-service change was made.
