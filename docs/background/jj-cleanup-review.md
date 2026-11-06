# Targeted jj cleanup

## My recommendation: A first

**Done:** removed only the local `reminders-s2` label. Its code remains in
`main`. **Nothing else below is approved or done.**

| Choice | What changes | Recommendation |
| --- | --- | --- |
| **A** | Remove 11 empty checkpoints. No source changes. | **Approve first:** least risk, biggest reduction. |
| **B** | Retire two source versions, including code/test differences. Backed up; not merged or repaired. | **Discuss next.** More risk than A. |
| **Old origin branches** | Delete `usual-items-redesign` and `wave2-bottom-bar` **from the server**, not just local labels. Behavior exists today; exact commits were not merged. | **Retire the names**, with separate approval. |
| **`groups`** | Real unfinished work; database migrations clash with today's app. | **Keep.** Port later; do not rebase for tidiness. |

### Tested result — not yet performed

```text
Now                 After A             After A + B
28 line ends   ──→  18 line ends   ──→   16 line ends
```

B would also archive one visible conflict and remove both visible divergent pairs.
Two parked conflicts would remain. **Keep `main`, local `integration` and
`integration@origin` unchanged.**

**Recovery:** I ran the isolated restore. Independent reviewers checked the
receipts, not a native rerun. Both configuration-related incidents were repaired.

---

## Details — open only what you need

<details>
<summary><strong>1. What changed, what stayed unchanged, and current commands</strong></summary>

Authority: [tracked assignment](../../plans/jj-history-review.md#owner-follow-up-targeted-cleanup).
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

This operation, not the earlier report's 969/28 snapshot, owns the current counts.
Report commits and empty working children can change later counts.

**Performed:** read-only local/remote inspection; own-empty entry rebase;
private recovery creation and isolated restore/retirement tests; this report;
a Lead-approved repair of the failed review's config-ID side effect below;
and the reviewed local `reminders-s2` label removal.
**Not performed:** abandonment, other bookmark changes, source rewriting,
fetch/push/server deletion, conflict repair, app/test changes or application tests.

## Local action receipt

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

Full change IDs and commits are in the linked evidence. Each row below identifies
one exact version; a short change ID alone is unsafe for divergence.

| Reference / exact commit / change ID | Accepted ancestry and unique content | Ownership / active use | Recommendation, command and recovery | Approval |
| --- | --- | --- | --- | --- |
| `reminders-s2` · `e50da7ce0a5456159f8206513c820e7180abbb8e` · `wlwznqlymtxmxynrrwmorpvqpzmnlnly` | Exact tip is an ancestor of `main`; zero unique commits. | Former S2 result; no S2 workspace. No known coordinated job, repository script or jj alias requires the name. Private owner aliases/external tools are not certified. | Removed local label with `jj bookmark forget exact:reminders-s2`. No descendants or source trees change. Restore with `jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e`. | Conditional owner permission used; independent review, live checks and Lead coordination passed. |
| `groups` / `groups@origin` · `2a46f1a4b3d4d588c14349e9f6bd733e3d50bb34` · `qwywttmonrutzsyrkrupkmykpmpmrlzy` | Five unique commits after common base `391b36fd141630206fb38978ac52fcd9334a89dc`; 57 feature-delta paths, +2,942/−84. Not accepted. | Owner's parked feature; current backlog retains it. No active implementation assigned here. | Keep exact original, source and remote name. No mutation command proposed. Use source inspection now; a later approved port can use an isolated copy. Recovery archive also retains it. | No rebase, repair or bookmark movement approved. |
| `usual-items-redesign@origin` · `3d1b2711825ef6e9da08d10bf90a76f54e1c8c2f` · `kvwywrsxpktluzqkmzroyzuoqstkspvy` | One unique commit after `a0185e1af6ff6a7c4ee6ffb130e8e6bcf977c519`; four paths, +47/−79. Not literally merged. Current Svelte popup implements the behavior. | Old remote feature name; no current coordinated owner. Source also lies under preview `aa6c85da`. | Propose exact guarded server deletion below, then refreshed tracking cleanup. Source remains visible under preview and in native archive. Merely forgetting the local cache would be temporary. | Exact remote name/command need owner approval. |
| `wave2-bottom-bar@origin` · `85c93c3428aca4daed9727e624ca176eb3cf3e22` · `vvsnkwnmstlruwxvtslvlqosuoxuwuyv` | One unique commit after the same base; 12 paths, +185/−67. Not literally merged. Current Svelte bar/toasts implement the behavior. | Old remote feature name; no current coordinated owner. Also under preview `aa6c85da`. | Same separate server/cache decision below. No source abandonment. | Exact remote name/command need owner approval. |
| `integration@origin` · `ddd687e25485c4707ad1ee7952da296e8987531f` · `krnplyqystqvuovpqlssroulzlxwpyxp` | Ancestor of local accepted integration; 139 commits behind at recovery snapshot. Local integration includes all of main and is 25 commits ahead of main. | Published/cached accepted-line position, not a disposable feature. | Keep. Behind does not mean broken. Removing this tracking state does not advance the published branch. Options/costs follow. | No tracking removal or push approved. |
| local `integration` · `ed08313afb1b4f5fc9571ddfb4d335db2a3266e5` · `rlswsnukyywpqlsrzzyzorypmnknuknz` | Current accepted baseline, including main and accepted runtime documentation. | Lead-owned; protected. | Keep unchanged. | Not moved by this task. |
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
contains full IDs, parents and membership. The native recovery test executed
sets A and B **only in a disposable repository**. No retained child had a removed
parent. No descendants were rebased. All exact sources survived in the archive.

### Set A — 11 empty checkpoints, ten fewer heads

Each single-parent empty leaf has an identical `jj debug tree` fingerprint to
its parent. The two-empty tail must be retired together: removing only its leaf
would expose its parent and save no head.

Retained representatives: accepted integration `ed08313a`; parked manual-source
spine `d10874b5`; fallback boundary `7d1c05b45183dc2f8e7ea34e43be8a5e2e069a92`.
The manual spine is **not reviewed/accepted product**, only a retained source
representative. No content is selected for reuse by this cleanup.

| Exact commit | Full change ID | Retained exact parent / representative | Decision / descendants / approval |
| --- | --- | --- | --- |
| `2f94b979c91a7031ae821bcb00cfe95b4ec101bb` | `nsxuyuvtrqvlwsupopvzpzwwwpwwwkyp` | Parent `216b2eabfd25b6467d64e97906601879ad723084` under `d10874b5`. | Archive/retire former research checkpoint; no descendants. Owner exact-set approval needed. |
| `e94ba514857ad7fdb15eebc304dc927c5f281aa5` | `pkwsulktwvnykvnwouyvywslruxnoumu` | Parent `e50da7ce0a5456159f8206513c820e7180abbb8e` under main/integration. | Archive/retire P2 review checkpoint; no descendants. Same gate. |
| `8bb5563fdf96e060594187d4621ab864bfd78895` | `mzmxtsymsvwsxpypnqqpmtmtoopwpxpx` | Parent `e85156425a66232f0e72078165b4c8f6b3d89092` under `d10874b5`. | Archive/retire reviewed UI/join checkpoint; no descendants. Same gate. |
| `2b7b53a00395e6ac3526f97e5df58b4f615d290d` | `mtytztrnmsqzszlxqsrssotysttvpswl` | Parent `1b3dd1e9b50eb34af152f966a6248a30cdfaf91a` under `d10874b5`. | Archive/retire combined-source checkpoint; no descendants. Same gate. |
| `4c653c9ea1e0aee85dee2aa82e89b76873da8f8a` | `xsqtvwmsnztlorpmuozzrknvnusqsxxm` | Parent `ce79907a8fbf837907aada8e7dae4a04fcd62e13` under `d10874b5`. | Archive/retire proof-review checkpoint; no descendants. Same gate. |
| `0aee179f4691eb701307a4a20c28acccac2bef07` | `rnmzuuypuqppquvlowpkmnynuzvvqvtx` | Parent `551819667e59e7f800648d5c7e354971f849fc1b` under `d10874b5`. | Archive/retire lifecycle checkpoint; no descendants. Same gate. |
| `d49ce34494232c50ed8b6558dcec7392b7de3153` | `ryovswotrzsxtlqnomxsnwkkzxyxqtlx` | Parent `f42c8ba6d85aa9c83cb562b1c0c17aa833c413a8` under integration. | Archive/retire reconciliation checkpoint; no descendants. Same gate. |
| `0ba13f05e82f9fd9a1dac13a95e2cf5564ad555b` | `pwoxuuotnqwlpxmmptmuznuyvpknpktp` | Parent `a8ee483af6deacd0331178790442f5edadbe2f60` under integration. | Archive/retire empty milestone; no descendants. Same gate. |
| `c650413ba10c240af0c50f2359691a2ae8ab3d59` | `rqskqvxzromytkltpvsnxlvuqrlwklsw` | Parent `62d6834c1db1c4faec425b6842ddf92abb088d8f` under integration. | Archive/retire empty foundation checkpoint; no descendants. Same gate. |
| `095fe95ea6724b191d8d3d6707575e4eca8bd106` | `ynltvomqotrlttrsrpuksntwousosyts` | Parent is the next row. | Archive/retire with its empty parent; no outside descendants. Same gate. |
| `95b1f504bd343cd74c464d39314ed1efa09d34df` | `qtkqlmwoqpzkloqypqtqroynmskoyozr` | Parent `7d1c05b45183dc2f8e7ea34e43be8a5e2e069a92` survives on retained lines. | Its only child is the preceding row. Retire together; same gate. |

These named review/resume points are not anonymous disposable leaves. Their
history and receipt identities belong in the archive even when their trees match.
Ownership/release is this exact-set owner decision, not an inference from age.
Execution commands, if approved, use one explicit `-r <full commit>` per row,
with the two-empty tail in one bounded operation. No broad `empty()` revset.
See [exact commands](jj-cleanup-review-evidence/proposed-commands.md).

**Exclude `fb60a3d8`.** Its empty leaf's parent `cd32f708` adds 251 lines and
removes six across five source/test files. Abandoning just that leaf replaces
one head with another; abandoning the tail would retire real repeat behavior.

### Set B — unused divergent leaf alternatives

| Archive/retire exact commit / change ID | Exact retained sibling | Lost-content comparison and dependencies | Gate |
| --- | --- | --- | --- |
| `31077a91123572b05e77baa41be804c6347967bb` / `qnuqpxvzsqsrxvkpzlyypqyzmkznlpvw` | `22ee5525fea92dbfe885cd123ff3d92f556893c6` | Retire leaf has no descendants. Retained sibling has 135 descendants. Source/test differences include scheduler wait/exception syntax, fixture naming and three tests absent on the retired alternative; runtime guide is conflicted. Not exact tree equality. Preserve both exact trees in archive. | Separate owner approval; no sibling rewrite. |
| `d8e8f9946cce76c82c06ad6c2533cc213a42ca2c` / `oltznxqwsylormtlnplowsszmznowuyu` | `c5ce1c843766b0a85d3020b27321730c730d9514` | Retire leaf has no descendants. Retained sibling has 143 descendants. Source/tests match; retained sibling also has a 74-line API guide and one index link. Preserve exact retired identity in archive. | Separate owner approval; no sibling rewrite. |

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

Deep conflict `6addc91115e22a0e8ce7b0c33486d9c0b7bd2e0c` has 153 visible
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
- Independent extraction, isolated HOME/config: all **988 visible exact metadata
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
- No application check is necessary or claimed for history/reference analysis.
  No Python, frontend, test, dependency or server behavior was changed.
- Outstanding exact decisions: A, B, the two remote feature names. Keep C and
  groups-port work separate. Acceptance/deployment remain separate gates.
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
- Lead owns this entry's lifecycle. The peer and entry stay available while the
  owner discusses exact A/B/remote decisions; no wider action is authorized.

</details>

