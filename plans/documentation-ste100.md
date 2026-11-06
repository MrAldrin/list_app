# Rewrite documentation in STE100 style

Lifecycle: tracked

## Status and outcome

The owner approved this assignment for **all first-party repository
documentation**, not only current guides. The [overnight run record](night-run.md)
owns execution approval, sequencing, operating limits, and stack destination.

Make the documentation easier to read without changing facts, requirements,
permissions, historical evidence, or product behavior. Use STE100-style writing:
short sentences, consistent terms, direct instructions, and clear paragraphs.
Do not claim formal STE100 compliance without checking the applicable rules and
controlled vocabulary.

The [backlog](backlog.md#next) owns this task's priority. This plan owns the
assignment; evidence and final page-by-page results belong in a background
report, not in a second work queue.

## Scope: everything, with protected content

Inventory all first-party documentation, including:

- README, architecture, glossary or other root documentation if present.
- User, API, developer, testing, deployment, and operational guides.
- Agent instructions, including repository `AGENTS.md` files.
- Backlog, active plans, batch briefs, and retained handoffs.
- Historical investigations, design notes, validation records, and other
  prose under `docs/background/`.
- Explanatory documentation in first-party source comments and docstrings.
- Human-readable prose in specifications where it can change without changing
  the specification's meaning or formal syntax.

All pages receive a recorded disposition: rewritten, already suitable, partly
protected, awaiting ownership, or blocked. Do not force a change to good text
just to make the diff larger. Do not describe a deferred page as reviewed.

Preserve these exactly unless a separate, verified correction is needed:

- Commands, code blocks, identifiers, paths, URLs, configuration values,
  schemas, formal specification statements, and examples whose exact content
  is significant.
- Raw logs, tool output, screenshots, checksums, test evidence, direct quotations,
  and externally authored material. Rewrite the surrounding explanation, not
  the evidence itself.
- License and attribution text.

Third-party packages, generated sites/build output, external agent settings,
private session transcripts, and the sibling reminder archive's raw evidence
are not repository-owned prose to rewrite. Do not follow symlinks outside the
repository or expose excluded/private files in the documentation preview.

## Requested agents and model authority

The owner explicitly requests:

- **Conductor:** use the selection in the [backlog](backlog.md#next).
- **Page writers:** `openai/gpt-6-luna`, thinking **xhigh** (extra-high), including
  straightforward pages. Do not lower effort based on cost estimates.
- Fresh independent review, separate from the page's writer. Requested review
  model: Luna/xhigh, with Conductor inspection and final disposition.

Both model IDs appear in the installed model list. Effective thinking settings
have not been verified in a child run; verify and record them at launch.

The current role policy uses Luna/xhigh for first-attempt bounded workers and
reviewers. The earlier Haiku-policy conflict is no longer active. Verify the
effective model and effort for each launch. Do not silently substitute another
model for the owner's explicit documentation choice.

## Style contract

Read the [official STE100 guidance](https://www.asd-ste100.org/about_STE.html)
and relevant specification sections before writing. Distinguish adopting
principles from formal compliance. Use practical technical English that fits
this app; preserve necessary technical terms.

- Put the purpose and main action first.
- Write short sentences with one main meaning.
- Use imperative sentences for instructions. Do not turn descriptions into
  commands or historical findings into current instructions.
- Use one topic per paragraph and explicit conditions.
- Prefer active voice when it makes the responsible person or system clear.
- Use the same name for the same thing. Establish a short terminology list
  from the actual app and authoritative docs before rewriting batches.
- Explain uncommon terms briefly where the audience needs it.
- Remove repetition only when all meaning and necessary links remain.
- Keep warnings, conditions, exceptions, and approval boundaries explicit.
- Follow the project's page-length and single-source-of-truth rules. Do not
  split, merge, move, delete, or retire documents merely to improve prose.

The owner values short, clear explanations. The result must not become longer
or more formal just to sound technical.

## Workflow and ownership

1. **Inventory:** list eligible files, audience, authority, current owner, and
   protected content. Separate current behavior, proposals, historical records,
   and instructions. Record the baseline revision.
2. **Calibrate:** rewrite a small representative batch: a guide, a technical
   contract, and a historical or instruction page. Review the style and factual
   fidelity before scaling to the remaining inventory. This is an internal
   quality checkpoint, not a request for the owner to approve every page.
3. **Assign:** give Luna/xhigh writers small batches with their original text,
   necessary source context, style rules, and explicit protected regions.
   Each concurrent writer gets a separate jj workspace.
4. **Review:** a fresh reviewer compares each candidate to its original and
   authoritative context. Check meaning, not just grammar. Resolve uncertainty
   before accepting a page into the candidate stack.
5. **Conductor check:** inspect actual diffs and review findings. Check headings,
   links, terminology, omissions, and changes to requirements. Read high-risk
   pages closely. Do not rewrite everything personally or rely only on worker
   summaries. Every page needs a documented review disposition.
6. **Verify and hand off:** run documentation and relevant code checks, update
   the inventory, and produce the morning report. Stop launching more batches
   in time to verify and preserve completed work.

### Instructions and historical records

For agent instructions and scope/approval documents, explicitly compare each
obligation, exception, and permission before and after. A simpler sentence must
not broaden authority, weaken a requirement, or turn a suggestion into a rule.
Use an additional Conductor review for these pages. Keep the active execution
contract stable; do not begin following a proposed rewrite of it mid-run.

Historical prose stays historical. Keep dates, exact source/change references,
reported-versus-verified distinctions, failures, and uncertainty. If a historical
statement differs from current behavior, label its historical context rather
than replacing the evidence with today's outcome.

### Concurrent overnight tasks

Do not rewrite a plan, backlog entry, report, or source file while another
agent owns an active edit window for it. Inventory it now and rewrite it after
the owner releases it. Coordinate handoff and re-read the latest source before
editing. Do not edit divergent shared-plan copies in feature workspaces.

Shared backlog and plan edits must be applied on the coordination docs desk,
in exclusive write windows, and committed with only the owned files. Do not
use this rewrite as authority to move agenda items or change other task scopes.

## Authority and limits

After execution approval, change documentation wording within the agreed scope.
No new product requirements, implementation, policy, services, dependencies,
pushes, deployment, production changes, or bookmark moves are authorized.
Normal docs-desk standing permissions still apply to the coordination owner,
not automatically to every worker.

Record source contradictions and suspected mistakes separately. Correct only
facts that can be established from authoritative evidence. Escalate changes
that would alter product behavior, an API contract, security/privacy rules,
agent authority, or an owner's decision. Do not guess the intended meaning.

Do not modify executable statements while editing comments/docstrings. Changes
to Python or frontend source files still require their repository quality gates;
calling the diff documentation-only does not waive those checks.

No new test framework, publishing setup, style-checking service, or dependency.
Use existing tools. Keep the local Zensical preview private, including its
current source exclusions. Coordinate heavy browser jobs with the test-suite
profiling task; the prose rewrite should not need its own browser matrix.

## Checks and acceptance

- Every inventoried page has a disposition; unfinished work is named explicitly.
- Each rewritten page has independent original-versus-rewrite review.
- Requirements, permissions, warnings, commands, numbers, and historical evidence
  retain their meaning. Protected content is unchanged except separately
  evidenced corrections.
- Source links and generated site links/anchors validate. Run
  `uv run python scripts/build_docs_site.py` and inspect its exit status and
  warnings. Do not say warning-free merely because the build succeeds.
- Keep useful inbound anchors stable, or update all maintained incoming links.
  Check references after any heading change.
- Run the required checks for any source files touched. No need to run a full
  app suite for Markdown-only batches unless a relevant project rule requires it.
- Verify the final candidate contains no unintended code, configuration,
  generated files, evidence deletion, or third-party modifications.

## Morning handoff

Write a dated report at `docs/background/documentation-ste100-review.md` with:

- Coverage of the documentation inventory: rewritten, already suitable,
  protected, deferred, and blocked files.
- A few concise before/after examples and the terminology/style decisions.
- Review outcomes, validation commands/results, and unresolved contradictions.
- Instruction/permission fidelity checks and any corrections needing approval.
- Exact change IDs, ownership, workspace and artifact locations, and cleanup
  state. Completed work must be recoverable without temporary workspaces.

Summarize that report for the owner. Do not claim all documentation is complete
if active files or unresolved pages were deferred. Keep the plan open until
those outcomes and follow-up work are recorded under its lifecycle rules.

## Execution record

- Priority, difficulty, and selected Conductor: see the [backlog](backlog.md#next).
- Owner-requested page writers and reviewers: Luna/xhigh.
- Model-policy conflict: resolved by the current role policy; effective-setting verification remains required at launch.
- Execution approval: [overnight run](night-run.md#approval-and-outcome).
- Conductor: `01a1adbe-bbbd-70a3-9663-4eb1ce3c8a22`, verified
  `openai/gpt-6.1-sol`, `low`; Zellij tab 18, pane 50 (`list_app-night-docs`).
- Large batch: all-document inventory, protected-content comparison, parallel
  page work, and independent original-versus-rewrite review.
- Workspace: `night-docs`, `/home/hsa/projects/list_app-night-docs`;
  Lead-created and agent-managed. Base: `night-1-tests-partial` (`oqpnzkyx`).
  Lead owns entry lifecycle; Conductor owns children. Lead report target:
  `01a1ad8b-c485-774e-bb47-66e425c18dc4`.
- Work window, concurrency, and artifact budget: [overnight run limits](night-run.md#run-limits-and-defaults).
- Shared-document write windows: completed and released. Lead committed only
  the independently reviewed shared plans on the desk.
- Result: `nkrslvrx` / `121fb5fd`, bookmarked `night-2-docs`; complete style pass,
  no formal STE100 certification. All 476 baseline paths accounted for; 52
  rewritten, 285 suitable, 79 protected/partly protected, 60 excluded/no prose.
  All 90 markup pages had full independent review. Unchanged source-comment
  independent review was sampled; every rewritten file had full comparison.
- Final audit `1b4723e1` found a combined privacy omission; restored in the
  actual entry and passed re-review `4ed40b68`. Raw BLOCK and PASS are retained.
- Python 1,792 passed; frontend 1,115 passed; formatting, lint, types, and build
  passed. Final docs build passed with 51 existing warnings, not warning-free.
  Lead repeated format/lint/type and docs-build checks: passed.
- Evidence: `docs/background/documentation-ste100-review.md`, inventory TSV,
  and tracked `documentation-ste100-evidence/` on the result line. Existing
  settings-visibility and “both apps” contradictions remain recorded, not fixed.
- Ten owned child workspaces and five job panes were removed at handback.
  On 2026-11-06 the owner approved entry/session cleanup before acceptance.
  Lead preserved `.night-docs-evidence/`, closed pane 50/tab 18, and removed
  `night-docs` and its folder. See the [cleanup record](night-run.md#retained-resources-and-next-decisions).
  The bookmarked candidate remains available. Task 1's browser failure remains.

## Progress

- [x] Record the all-document scope, requested models, and fidelity safeguards.
- [x] Record owner-selected backlog placement and Conductor.
- [x] Resolve worker-model authority and approve execution limits.
- [x] Inventory documents and establish the terminology/style contract.
- [x] Calibrate, rewrite batches, and independently review the actual changes.
- [x] Finish or explicitly account for active/protected/deferred documents.
- [x] Validate the final candidate and deliver the task report.
- [x] Preserve ignored evidence and remove the entry/session under owner approval.
- [ ] Owner inspects the unaccepted candidate and addresses or records the factual
  contradictions before this tracked plan is retired.
