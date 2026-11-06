# Targeted jj cleanup

## Batch closed — further review is deferred

**Completed:** the local `reminders-s2` label removal, **11 empty checkpoints (A)**
and **two unused source alternatives (B)**. No app code or protected reference
changed. **Remote deletion is still unapproved.**

| Choice | Status | Recommendation |
| --- | --- | --- |
| **A · Done** | Retired 11 empty checkpoints. Ten fewer line ends. | Complete. |
| **B · Done** | Retired two unused source versions. Their code/test differences remain archived—not merged or repaired. | Complete. Retained versions and descendants stayed unchanged. |
| **Old origin branches · Pending** | Delete `usual-items-redesign` and `wave2-bottom-bar` **from the server**, not just local labels. Behavior exists today; exact commits were not merged. | **Retire the names**, with separate approval. |
| **`groups`** | Real unfinished work; database migrations clash with today's app. | **Keep.** Port later; do not rebase for tidiness. |

### Actual result

```text
Before              After A             Now: A + B
28 line ends   ──→  18 line ends   ──→   16 line ends
```

There are now **two parked conflicts and no divergent pairs**. B archived the
unused alternatives; it did not repair their code.
**During A/B execution, `main`, local `integration` and `integration@origin`
stayed unchanged.** Later report acceptance is recorded below.

The remaining line ends include protected workspaces and real parked work.
They are not all candidates for removal.

**Recovery:** I ran the isolated restore; independent reviewers checked receipts,
not a native rerun. The archive is unchanged. Both configuration-related incidents
were repaired.

## Closeout

The owner accepted the report and evidence into `integration`, then closed
this batch. Another history review is in [Later](../../plans/backlog.md#later).
No remote deletion or additional history cleanup is approved.

- Lead rebased the report-only line onto the accepted baseline. All 62 reviewed
  report/evidence blobs matched original `62b9a607` exactly before this closeout
  note. Accepted report tip: `7c3372c41793cb2c2b02969b261e498f46f49376`.
- The Conductor is closed; `jj-cleanup` registration and folder are removed.
  Other task sessions/workspaces were closed separately; old pre-existing
  workspaces and the owner's docs server are untouched.
- Original report commits remain in the private recovery directory's
  `completed-report.bundle`, SHA-256
  `052cb8e67e3b5d03572e53da1ed95668d7085ae46478276ae65127b88ebb3364`.
  Lead verified an import into an empty bare Git repository, full ancestry,
  five exact commit bodies/trees and all 62 evidence entries. This is backup
  verification, not a new native jj restore. Keep the native tar and raw A/B
  receipts described below too. Do not publish these private files.
- The completed tracked assignment is retired. Its final pre-integration
  snapshot remains at `6f91c3fb`, path `plans/jj-history-review.md`.

---

## Details — open only what you need

<details>
<summary><strong>1. What changed, what stayed unchanged, and current commands</strong></summary>

Authority: the owner-approved assignment, archived at `6f91c3fb` as
`plans/jj-history-review.md`. Further work needs fresh owner approval.
Conductor: `01a1afc6-f7c5-76e5-a8cf-9622e5f80bfe`, `openai/gpt-6.1-sol`, `high`.
Entry `jj-cleanup` is Lead-created/managed. Shared plans/backlog remain Lead-owned.

## Snapshot and action status

The first read-only snapshot had 986 visible commits and 29 heads. The runtime
report was then separately accepted and its creator removed its workspace.
This task rebased **only its own confirmed-empty entry** onto accepted
`ed08313afb1b4f5fc9571ddfb4d335db2a3266e5`, producing `343493e0`.

The recovery snapshot has **988 visible commits, 28 heads, three conflicted
commits and four divergent versions**. Operation:

`f6e9450d01c4e22635b646e9038ac50980a99903124bfb7e5adc15f6a0cd878d59bf692b1032c78c83c8e49549299b02be248946281f3f58ac1328adf6ce226d`

This operation records the recovery baseline, not the later live counts.
The A/B execution receipts below are newer.

**Performed:** read-only local/remote inspection; own-empty entry rebase;
private recovery creation and isolated restore/retirement tests; this report;
a Lead-approved repair of the failed review's config-ID side effect below;
the reviewed local `reminders-s2` label removal; and owner-approved A/B retirement.
**Not performed:** other abandonment, other bookmark changes, retained-source
rewriting, fetch/push/server deletion, conflict repair, app/test changes or application tests.

## Set B execution receipt

The owner approved exact B and execution after checks. The Lead granted a B-only
window. Two singleton operations passed, in the original command order:
`d8e8f9946cce76c82c06ad6c2533cc213a42ca2c`, then
`31077a91123572b05e77baa41be804c6347967bb`.

- Immediate counts: **983 → 981 visible commits; 18 → 16 heads;
  3 → 2 conflicts; 4 → 0 divergent versions**.
- Exact retained siblings `c5ce1c843766b0a85d3020b27321730c730d9514` and
  `22ee5525fea92dbfe885cd123ff3d92f556893c6` kept all source and descendants.
  Only their native divergence flags cleared, each after its paired alternative
  was retired. No other retained native fields changed.
- Complete retained Git bodies/tree IDs, refs, tags, workspaces, config and
  **79 protected exact tree fingerprints** stayed unchanged. This includes the
  36 old resume sources and all 11 earlier A checkpoints.
- Both retired B exact trees still read back and match the unchanged archive.
  This is archival retirement—not a merge, code repair or feature acceptance.
  No remote, tracking, bookmark or GC action was run.

Post-operation:
`c5e4e9f59787f51cf2823d1d8ba9da1470d3177cdf73f4a5f25ee11eb3231c85f641fb1498dce7022209567eaa8661cf936c2f0bcafd04a41f13d6663292d9d4`.

The first [native preflight stopped](jj-cleanup-review-evidence/set-b-descendant-preflight-stop.json)
before retirement: historical descendant counts 135/143 were incorrectly used
as current minima after A. The corrected guard reconciled exact identities
against frozen A.after and the two attributable report/desk replacements and
their children. Retained descendant sets are now **128/136**, unchanged since
A's action; no unexplained dependency change was accepted.
The [independent static preflight](jj-cleanup-review-evidence/set-b-preflight-review.md)
passed before action. The original stopped method and state remain preserved.
The [initial B post-audit](jj-cleanup-review-evidence/set-b-post-action-initial-review.md)
passed all executed-state checks but blocked on historical-versus-live head IDs.
The frozen manifest is unchanged; the head-provenance record separates its
recovery snapshot from the actual B execution. The [Haiku correction](jj-cleanup-review-evidence/set-b-partial-correction-review.md)
then stopped on a parser schema error; it did not find a repository failure.
The [independent Lead static correction](jj-cleanup-review-evidence/set-b-lead-correction-review.md)
**passed** after actually recomputing both projections, both cursor lineages
and the 14 unchanged head IDs. This closes provenance only; it does not replace
Haiku's successful executed-state checks or claim a native rerun.

See [fresh B preflight](jj-cleanup-review-evidence/set-b-preflight.json),
[two-operation receipt](jj-cleanup-review-evidence/set-b-execution.json) and
[private raw-file index](jj-cleanup-review-evidence/set-b-receipt-index.json).
Report updates and clean working children can change later commit counts.

## Set A execution receipt

The owner approved exact Set A and then clarified **execute it now**. The Lead
granted an exclusive window for A only. All ten operations passed: nine single
empty leaves, then the two-empty tail together.

- Immediate action counts: **992 → 981 visible commits; 28 → 18 heads**.
  Report updates and the clean working child can change later commit counts.
- All retained complete Git commit bodies and tree IDs matched. Full native jj
  descriptions, change IDs, parents, flags and visibility also matched.
- All bookmarks, tags, workspace pointers, critical refs and **67 protected exact
  trees** stayed unchanged, including all 36 archived old resume sources.
- No retained child was rewritten and no parent became a new head. All 11 retired
  exact trees still read back and match the unchanged recovery archive.
- Conflicts/divergent versions stayed **3/4**. B, remote cleanup and GC were not run.

Post-operation:
`d6c483329ec4aff369885a98e16b3486ff19ac043f8c98d28e94a4a4bcf845e817037e38ac978e51b0a9745a1d2bf4d104358e375ea953660d8e63516084806e`.

The first [static preflight review](jj-cleanup-review-evidence/set-a-blocked-review.md)
**blocked** an incomplete metadata guard before any retirement. The guard was
strengthened, not waived. The [escalated review](jj-cleanup-review-evidence/set-a-escalated-review.md)
and [correction review](jj-cleanup-review-evidence/set-a-correction-review.md)
passed. These were static reviews, not independent native reruns.
The first [post-action review](jj-cleanup-review-evidence/set-a-post-action-blocked-review.md)
was blocked by missing Python capability, not a repository failure. The final
[Terra/Medium audit](jj-cleanup-review-evidence/set-a-post-action-review.md)
**passed**: it independently hashed all 43 indexed files and compared all ten
full state maps, including 9,864 retained entries and 130 protected-field checks.
It did not rerun native operations, restoration or tree readbacks.

See the [fresh preflight](jj-cleanup-review-evidence/set-a-preflight.json),
[ten-operation receipt](jj-cleanup-review-evidence/set-a-execution.json) and
[private raw-receipt index](jj-cleanup-review-evidence/set-a-receipt-index.json).
The original failed guard, corrected method and per-step states are retained.

## Local action receipt — reminders-s2

Executed only `jj bookmark forget exact:reminders-s2`, exit 0, under the owner's
conditional permission. Pre-operation `16f184ff…8144`; post-operation
`dc507677…9258`. Full operation IDs, command output, exact references, workspace
and tree checks are retained in the
[protected-state receipt](jj-cleanup-review-evidence/local-forget-protected-check.json)
and paired before/after records. The action did not remove any source or head.
Main, integration, groups, all five night results, diagnostic, old workspaces,
origin refs, both archive checksums and the repaired config ID stayed unchanged.

If the label is needed again, the exact inverse is:

```sh
jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e
```

Do not run a broader operation restore for this label. No inverse was needed.

## Current commands remain valid without the old name

Repository scripts and configured jj aliases have no `reminders-s2` dependency.
Coordinated Lead/test agents report no active or queued use. Owner-private aliases
and external tools are not certified. Historical receipts remain unchanged.
This current view tolerates the name's removal; run the attention view too:

```sh
jj --ignore-working-copy --at-op=@ log -r 'main | integration | groups | present(reminders-s2) | bookmarks(glob:"night-*") | @ | parents(@)'
jj --ignore-working-copy --at-op=@ log -r 'conflicts() | divergent()'
```

A filtered view does not count as physical cleanup. The exact A/B tests above do.

</details>

<details>
<summary><strong>2. Exact branch-name decisions and why groups should stay</strong></summary>

## Named references: exact decisions

This table records the recovery snapshot. For Set A, the newer accepted integration
`37fedeecced9ad63080f7e468aa691b23f4d0b96` was protected and stayed unchanged;
see the fresh A preflight above. B protected the still newer accepted target
`9e454f554ae861b6027abcd3705a093e4d0b4548`, also unchanged by cleanup.

Full change IDs and commits are in the linked evidence. Each row below identifies
one exact version; a short change ID alone is unsafe for divergence.

| Reference / exact commit / change ID | Accepted ancestry and unique content | Ownership / active use | Recommendation, command and recovery | Approval |
| --- | --- | --- | --- | --- |
| `reminders-s2` · `e50da7ce0a5456159f8206513c820e7180abbb8e` · `wlwznqlymtxmxynrrwmorpvqpzmnlnly` | Exact tip is an ancestor of `main`; zero unique commits. | Former S2 result; no S2 workspace. No known coordinated job, repository script or jj alias requires the name. Private owner aliases/external tools are not certified. | Removed local label with `jj bookmark forget exact:reminders-s2`. No descendants or source trees change. Restore with `jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e`. | Conditional owner permission used; independent review, live checks and Lead coordination passed. |
| `groups` / `groups@origin` · `2a46f1a4b3d4d588c14349e9f6bd733e3d50bb34` · `qwywttmonrutzsyrkrupkmykpmpmrlzy` | Five unique commits after common base `391b36fd141630206fb38978ac52fcd9334a89dc`; 57 feature-delta paths, +2,942/−84. Not accepted. | Owner's parked feature; current backlog retains it. No active implementation assigned here. | Keep exact original, source and remote name. No mutation command proposed. Use source inspection now; a later approved port can use an isolated copy. Recovery archive also retains it. | No rebase, repair or bookmark movement approved. |
| `usual-items-redesign@origin` · `3d1b2711825ef6e9da08d10bf90a76f54e1c8c2f` · `kvwywrsxpktluzqkmzroyzuoqstkspvy` | One unique commit after `a0185e1af6ff6a7c4ee6ffb130e8e6bcf977c519`; four paths, +47/−79. Not literally merged. Current Svelte popup implements the behavior. | Old remote feature name; no current coordinated owner. Source also lies under preview `aa6c85da`. | Propose exact guarded server deletion below, then refreshed tracking cleanup. Source remains visible under preview and in native archive. Merely forgetting the local cache would be temporary. | Exact remote name/command need owner approval. |
| `wave2-bottom-bar@origin` · `85c93c3428aca4daed9727e624ca176eb3cf3e22` · `vvsnkwnmstlruwxvtslvlqosuoxuwuyv` | One unique commit after the same base; 12 paths, +185/−67. Not literally merged. Current Svelte bar/toasts implement the behavior. | Old remote feature name; no current coordinated owner. Also under preview `aa6c85da`. | Same separate server/cache decision below. No source abandonment. | Exact remote name/command need owner approval. |
| `integration@origin` · `ddd687e25485c4707ad1ee7952da296e8987531f` · `krnplyqystqvuovpqlssroulzlxwpyxp` | Ancestor of local accepted integration; 139 commits behind at recovery snapshot. Local integration includes all of main and is 25 commits ahead of main. | Published/cached accepted-line position, not a disposable feature. | Keep. Behind does not mean broken. Removing this tracking state does not advance the published branch. Options/costs follow. | No tracking removal or push approved. |
| local `integration` · `ed08313afb1b4f5fc9571ddfb4d335db2a3266e5` · `rlswsnukyywpqlsrzzyzorypmnknuknz` | Accepted baseline at the recovery snapshot, including main and accepted runtime documentation. | Lead-owned; protected. | Keep unchanged. | Not moved by this task. |
| `main` · `250c17b669605cea59bd671ba7e9e49ee3dcbce6` · `xsqznkopupwtxwtwnwosrlksryoxzpmw` | Production line; protected. | Owner-controlled deployment. | Keep unchanged. | No deployment or push approved. |

### Groups: worth keeping, not ready to replay

The source implements room-authorized group create/update/delete, ordered names,
a room catalog in feeds/snapshots, add-if-absent, offline queue replay, optimistic
UID remapping, partial results and editor/add UI. It is more than a plan.

Its migration 15 creates named groups and migration 16 adds tombstone retention.
Today's accepted migrations 15–18 already serve due time, private reminders,
due-cycle start and policies. A port must add new migrations **after 18**, not
reuse old numbers. Database, feed, name-key, item-write and queue contracts also
need reconciliation. No isolated rebase or application check was run here.

The old groups delivery record claims tests for an earlier delivered source.
Later `bc9a5f1e` and `2a46f1a4` contain additional source/test changes. Those old
receipts are not a fresh check of today's baseline. The current groups plan is
stale about implementation; the Lead can update that shared plan separately.
See [bounded source analysis](jj-cleanup-review-evidence/groups-refs-scout.md).

### Origin names: server and local cache are different

Read-only `git ls-remote --heads origin` succeeded at
`2026-11-06T07:39:45.976288Z`. All five live server tips matched the cache:
main, groups, integration, usual-items-redesign and wave2-bottom-bar.
No URL, credential, fetch or push was needed for the receipt.

**Proposal only**, for the two exact obsolete server feature names:

```sh
git push --force-with-lease=refs/heads/usual-items-redesign:3d1b2711825ef6e9da08d10bf90a76f54e1c8c2f origin :refs/heads/usual-items-redesign
git push --force-with-lease=refs/heads/wave2-bottom-bar:85c93c3428aca4daed9727e624ca176eb3cf3e22 origin :refs/heads/wave2-bottom-bar
```

These guarded commands refuse deletion if the server tip moved. Recheck live
heads first. After approved deletion, fetch in the exclusive graph window to
refresh tracking. Neither name is local `main` or `integration`. Removal does
not delete commits; preview `aa6c85da` still retains both exact feature sources.

If the owner wants **local cache-only cleanup** instead, the following command
passed in the disposable repository, but is **not approved or run live**:

```sh
jj bookmark forget --include-remotes exact:usual-items-redesign exact:wave2-bottom-bar
```

A later fetch recreates those references while the server branches exist. It
saves two local labels but does not retire server branches or reduce heads.
Server-name restoration, if later required, needs another explicit push decision
using the archived exact tips; it is not an automatic undo step.

For `integration@origin`:

- **Keep tracking — recommended:** preserves the published baseline and drift
  evidence. No mutation or cost beyond one old label.
- **Untrack it:** `jj bookmark untrack integration@origin` would stop tracking,
  but keep the cached reference and local integration. It does not simplify
  source history or fix drift. Proposal only.
- **Publish local integration:** updates the server's accepted-line position,
  not production main. This is a separate push decision, not cleanup authority.
- **Delete the server integration branch:** removes a shared published baseline;
  local integration must stay. This has little benefit and requires an exact
  owner decision. Do not forget local integration to hide its remote label.

</details>

<details>
<summary><strong>3. A, B and the deferred C option: exact IDs and commands</strong></summary>

## Physical graph reduction: exact sets, not log filters

The [exact-set manifest](jj-cleanup-review-evidence/proposed-exact-sets.json)
contains full IDs, parents and membership. Its head arrays and combined visible
counts freeze operation `f6e9450d`; they are not later live-head claims.
The [head-provenance record](jj-cleanup-review-evidence/set-b-head-provenance.json)
proves the historical projection and the two later workspace-cursor replacements.
Current projections are in the A/B preflight receipts. The native recovery test executed
sets A and B in a disposable repository first. **A is now executed live with owner
approval; B is now also executed with separate owner approval.** No retained
child was rewritten.
All exact sources survive in the archive.

### Set A — completed: 11 empty checkpoints, ten fewer heads

The owner released this exact set. All eleven rows below were retired; their
parent/descendant facts describe the verified pre-action state.

Each single-parent empty leaf has an identical `jj debug tree` fingerprint to
its parent. The two-empty tail must be retired together: removing only its leaf
would expose its parent and save no head.

Retained representatives: accepted integration `ed08313a`; parked manual-source
spine `d10874b5`; fallback boundary `7d1c05b45183dc2f8e7ea34e43be8a5e2e069a92`.
The manual spine is **not reviewed/accepted product**, only a retained source
representative. No content is selected for reuse by this cleanup.

| Exact commit | Full change ID | Retained exact parent / representative | Decision / descendants / approval |
| --- | --- | --- | --- |
| `2f94b979c91a7031ae821bcb00cfe95b4ec101bb` | `nsxuyuvtrqvlwsupopvzpzwwwpwwwkyp` | Parent `216b2eabfd25b6467d64e97906601879ad723084` under `d10874b5`. | Retired former research checkpoint; no descendants. Owner-approved; retired. |
| `e94ba514857ad7fdb15eebc304dc927c5f281aa5` | `pkwsulktwvnykvnwouyvywslruxnoumu` | Parent `e50da7ce0a5456159f8206513c820e7180abbb8e` under main/integration. | Retired P2 review checkpoint; no descendants. Owner-approved; retired. |
| `8bb5563fdf96e060594187d4621ab864bfd78895` | `mzmxtsymsvwsxpypnqqpmtmtoopwpxpx` | Parent `e85156425a66232f0e72078165b4c8f6b3d89092` under `d10874b5`. | Retired reviewed UI/join checkpoint; no descendants. Owner-approved; retired. |
| `2b7b53a00395e6ac3526f97e5df58b4f615d290d` | `mtytztrnmsqzszlxqsrssotysttvpswl` | Parent `1b3dd1e9b50eb34af152f966a6248a30cdfaf91a` under `d10874b5`. | Retired combined-source checkpoint; no descendants. Owner-approved; retired. |
| `4c653c9ea1e0aee85dee2aa82e89b76873da8f8a` | `xsqtvwmsnztlorpmuozzrknvnusqsxxm` | Parent `ce79907a8fbf837907aada8e7dae4a04fcd62e13` under `d10874b5`. | Retired proof-review checkpoint; no descendants. Owner-approved; retired. |
| `0aee179f4691eb701307a4a20c28acccac2bef07` | `rnmzuuypuqppquvlowpkmnynuzvvqvtx` | Parent `551819667e59e7f800648d5c7e354971f849fc1b` under `d10874b5`. | Retired lifecycle checkpoint; no descendants. Owner-approved; retired. |
| `d49ce34494232c50ed8b6558dcec7392b7de3153` | `ryovswotrzsxtlqnomxsnwkkzxyxqtlx` | Parent `f42c8ba6d85aa9c83cb562b1c0c17aa833c413a8` under integration. | Retired reconciliation checkpoint; no descendants. Owner-approved; retired. |
| `0ba13f05e82f9fd9a1dac13a95e2cf5564ad555b` | `pwoxuuotnqwlpxmmptmuznuyvpknpktp` | Parent `a8ee483af6deacd0331178790442f5edadbe2f60` under integration. | Retired empty milestone; no descendants. Owner-approved; retired. |
| `c650413ba10c240af0c50f2359691a2ae8ab3d59` | `rqskqvxzromytkltpvsnxlvuqrlwklsw` | Parent `62d6834c1db1c4faec425b6842ddf92abb088d8f` under integration. | Retired empty foundation checkpoint; no descendants. Owner-approved; retired. |
| `095fe95ea6724b191d8d3d6707575e4eca8bd106` | `ynltvomqotrlttrsrpuksntwousosyts` | Parent is the next row. | Retired with its empty parent; no outside descendants. Owner-approved; retired. |
| `95b1f504bd343cd74c464d39314ed1efa09d34df` | `qtkqlmwoqpzkloqypqtqroynmskoyozr` | Parent `7d1c05b45183dc2f8e7ea34e43be8a5e2e069a92` survives on retained lines. | Its only child is the preceding row. Retired together with owner approval. |

These named review/resume points are not anonymous disposable leaves. Their
history and receipt identities belong in the archive even when their trees match.
Ownership/release is this exact-set owner decision, not an inference from age.
Execution used one explicit `-r <full commit>` per row, with the two-empty tail
in one bounded operation. No broad `empty()` revset was used.
See [exact commands](jj-cleanup-review-evidence/proposed-commands.md).

**Exclude `fb60a3d8`.** Its empty leaf's parent `cd32f708` adds 251 lines and
removes six across five source/test files. Abandoning just that leaf replaces
one head with another; abandoning the tail would retire real repeat behavior.

### Set B — completed: two unused divergent leaf alternatives

The owner released both exact alternatives below. The comparison and dependency
counts in this table describe the recovery snapshot, before A retirement.
Both retained source trees and Git commit objects remain unchanged. The newer
B receipt above records the exact native divergence-flag changes.

| Archive/retire exact commit / change ID | Exact retained sibling | Lost-content comparison and dependencies | Gate |
| --- | --- | --- | --- |
| `31077a91123572b05e77baa41be804c6347967bb` / `qnuqpxvzsqsrxvkpzlyypqyzmkznlpvw` | `22ee5525fea92dbfe885cd123ff3d92f556893c6` | Retire leaf has no descendants. Retained sibling had 135 descendants at the recovery snapshot. Source/test differences include scheduler wait/exception syntax, fixture naming and three tests absent on the retired alternative; runtime guide is conflicted. Not exact tree equality. Preserve both exact trees in archive. | Separately owner-approved and retired; no sibling rewrite. |
| `d8e8f9946cce76c82c06ad6c2533cc213a42ca2c` / `oltznxqwsylormtlnplowsszmznowuyu` | `c5ce1c843766b0a85d3020b27321730c730d9514` | Retire leaf has no descendants. Retained sibling had 143 descendants at the recovery snapshot. Source/tests match; retained sibling also has a 74-line API guide and one index link. Preserve exact retired identity in archive. | Separately owner-approved and retired; no sibling rewrite. |

The descendant sets overlap; do not add their counts. Neither retained sibling
is claimed to equal later reviewed scheduler/API checkpoints: direct comparisons
show further source/test changes. Retention here follows dependency preservation
and exact archival, not a claim that fewer lines means better code.

After A/B, the native disposable test had 16 heads, two conflicts and zero
visible divergence pairs. Restoring the saved archive recovered all original
metadata and source, including both alternatives and all three conflicts.

### Other lines: no automatic retirement

The four-commit early-polish tail is a possible **later** archive set C, not
selected for execution: `182b071f`, `53f76283`, `16b15aea`, `ad79662f` (full IDs
in manifest). It includes a conflicted merge, its resolution, and settings/strip
test work. Compared with boundary `e8515642`, 15 paths differ. It is not redundant
source. It would remove one further head and the early-P conflict, by archival
retirement, not by repair or product acceptance.

At the recovery snapshot, deep conflict
`6addc91115e22a0e8ce7b0c33486d9c0b7bd2e0c` had 153 visible
descendants at the first snapshot. Rewriting it can affect most reminder lines.
Keep it parked. Keep paused manual WIP `d10874b5`, nonempty repeat/push/restore
outliers, the preview merge, all five night result bookmarks, task-1 diagnostic
`d2c6a988`, retained `night-tests`, and both old temporary workspaces. The evidence
[head decision table](jj-cleanup-review-evidence/head-decisions.md) records every
exact head, unique tail and ownership boundary; no unrelated empty workspace tip
is included.

</details>

<details>
<summary><strong>4. Recovery archive, safeguards and both incidents</strong></summary>

## Durable recovery and limits

Private local archive, outside both working repositories and the old reminder
archive:

`/home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/native-history.tar`

- Size: **160,430,080 bytes**; SHA-256:
  `e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d`.
- Self-contained native jj metadata plus all Git objects/refs. No hard links,
  symlinks or object alternates; relative Git-store path is valid after extraction.
- No project working files, `.env`, app databases, dependency caches, Git remote
  config or hooks. The portable Git config is minimal and has no remotes. The
  directory is mode 0700; archive/receipts are private. Do not publish the archive.
- Conductor-run extraction, isolated HOME/config: all **988 visible exact metadata
  records** and **1,024 exact tree fingerprints** matched. These include every
  visible commit and all 36 old exact archive resume commits.
- After disposable retirement tests, a **new extraction from the archive** again
  restored 988/1,024 matches. This did not rely on operation undo or live objects.
  All 1,024 restored tree lookups were traced: no original repository/workspace/
  reminder-archive path and no Internet socket access. See
  [restore receipt](jj-cleanup-review-evidence/restore-final-receipt.json).
- The outer tracing wrapper reached its 60-second timeout after writing the
  successful verification receipt. A separate streaming scan of the full trace
  passed. No test process remained. This timeout is not reported as an exit-0 run.
- One extra disposable cache-forget test omitted isolated HOME. jj made a small
  per-repo config copy for that disposable location. Only that attributable copy
  was removed; the original config was not edited and its contents were not
  printed. Subsequent disposable commands use isolated HOME/config.
- The first independent review was **BLOCKED**: it launched sandbox jj with
  `-R` while its cwd was the live workspace, despite isolated HOME/config. jj
  loaded cwd configuration and changed the live `.jj/repo/config-id` from
  `73360a744b7debff796b` to `933f2e6c443e922f61c5`. All reviewer jj stopped.
  With explicit Lead approval, only that identifier was restored to exact bytes
  verified against both untouched staging and archive; mode 0600 was preserved.
  Original user config contents were not read or edited. Only the new owned
  isolated metadata was removed; the incident evidence remains private and the
  [repair receipt](jj-cleanup-review-evidence/reviewer-config-id-incident.json)
  is retained. The revised guide sets physical sandbox cwd before jj starts and
  rejects live pointers/alternates. An escalated fresh review must pass.
- Old `/home/hsa/projects/reminders-archive` is unchanged. All 36 exact source
  commits resolve; 26 mapped change IDs have visible versions, ten are hidden-only.
  The old resume checksum matches. An old operation or ordinary Git object alone
  is not treated as a durable backup.

The [restore instructions](jj-cleanup-review-evidence/recovery-guide.md) show how
to inspect a private extraction without reconnecting to the live repository.
Restoring source into the live graph needs a new coordinated, reviewed exact
plan. Never run a broad `op restore` in the active repository to recover one leaf.

</details>

<details>
<summary><strong>5. Reviews, checks, budget and retained artifacts</strong></summary>

## Checks, reviews and owner decisions

- Bounded ancestry/source scout `2e24b414` completed. Host status verifies
  `openai/gpt-6-luna`, `xhigh`; the scout could not attest its own host tier.
- Independent review `e207218b`: **BLOCKED / failed safety check**, not a pass.
  It also received the parent's stale-manifest finding. That manifest's survivor
  arrays/counts are now refreshed to the actual recovery snapshot: 28 → 18 → 16.
  Escalated static review `86787486` independently verified the archive hash,
  member safety, corrected sets/counts, ancestry, dependencies and budget sum.
  It passes the conditional local-name gate after live pre-checks and Lead
  coordination. Its guide-isolation and receipt-label findings were corrected;
  narrow static follow-up `fcbe2181` **passed** with no remaining guide/label
  blocker. No native test was rerun by that reviewer. See [review disposition](jj-cleanup-review-evidence/review-disposition.md).
- Conditional local bookmark action and post-action protected-state checks:
  **passed**. All 988 visible commit records and all workspace targets stayed
  identical; 52 protected exact trees, including all 36 old resume sources,
  match. Heads/conflicts/divergent versions stayed 28/3/4. Only the expected
  local label and its local Git mirror disappeared. Coordinated agents report
  no known live symbolic-name dependency;
  owner-private aliases/external tools were not inspected or certified.
- [Post-action static review](jj-cleanup-review-evidence/post-action-review.md)
  `7538d73a` **passed**. Haiku/max independently compared the actual recorded
  metadata, reference, workspace, tree, checksum, cleanup and budget receipts.
  Live checks remain parent-run; no independent native rerun is claimed.
- No application check is necessary or claimed for history/reference cleanup.
  No application Python, frontend, test, dependency or server behavior was changed.
- A and B are owner-approved and performed. Outstanding exact decisions: the
  two remote feature names. Keep C and groups-port work separate.
  Report acceptance/deployment remain separate gates.
- [Final budget/link check](jj-cleanup-review-evidence/final-budget-and-links.json):
  retained overnight evidence plus this task's known generated roots measured
  1,956,982,784 allocated bytes after temporary-copy cleanup. A conservative peak
  bound is 2,705,956,864 bytes, below 3 GiB (3,221,225,472 bytes). Free space was
  14,047,449,088 bytes, above the 6 GiB floor. The bound includes later review
  records with deliberate double-counting and a margin, not an invented exact
  peak measurement. All delivered JSON parses and report links resolve.
- [Owned recovery cleanup](jj-cleanup-review-evidence/owned-recovery-cleanup.json):
  removed only standalone staging, two restore-test copies and their isolated
  HOME after archive verification and process-cwd checks. These were independent
  copies, not registered shared workspaces. Retained the private native archive,
  traces, methods and incident/restore receipts. No child workspace was created.
- [Set A budget check](jj-cleanup-review-evidence/set-a-budget.json) adds the new
  receipt copies, review records and a margin to the prior conservative peak.
  No new native recovery copy was made. The [scratch cleanup receipt](jj-cleanup-review-evidence/set-a-owned-scratch-cleanup.json)
  records removal of 41 verified temporary files; the private copies remain.
- [Set B budget check](jj-cleanup-review-evidence/set-b-budget.json) includes both
  receipt copies and later review records. No new native recovery copy was made.
  [B scratch cleanup](jj-cleanup-review-evidence/set-b-owned-scratch-cleanup.json)
  removed 19 verified phase files and five auditor-created scripts after their
  private copies were preserved.
- Lead completed the entry lifecycle at the owner's closeout request. The peer
  and workspace are removed; remaining decisions are deferred, not approved.

</details>

