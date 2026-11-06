# Independent read-only review: targeted jj cleanup

**Overall: FAIL for cleanup acceptance pending two corrections.** The specific
local `reminders-s2` label-removal proposal passes its separate conditional
review gate; that does not approve set A, set B, remote-name deletion, or any
live mutation. No source edit, live bookmark change, abandon, fetch, push,
remote command, app check, or test was performed by this reviewer.

## Findings

### P1 — Fresh restore inspection stopped on an unexpected repo-config warning

I independently checked the archive file itself: `sha256sum` returned
`e703ef0567c351c41c1f195603656c297af08290d7063cafdf41181fa24ffb604d`, and
`stat` reported 160,430,080 bytes, mode 0600. The existing receipts are
substantial: `restore-final-receipt.json:2-12` says the archive was re-extracted
after the retirement simulation, 988 native metadata records and 1,024 trees
matched, all lookups were traced without repository/workspace/archive paths or
network access, and the separate streaming trace check passed. It also
accurately records that the outer wrapper timed out after the verification
receipt; that is not an exit-0 claim. Report lines 203-229 disclose the
per-repository-config incident from the earlier disposable cache-forget test
(237 bytes in two files, exact attributable copy removed, original config
untouched, no config contents printed). Nothing here supports claiming all
commands were always isolated or side-effect-free.

However, my attempted fresh read-only inspection did **not** validate those
receipts. I launched the following class of commands from
`/home/hsa/projects/list_app-jj-cleanup` (the cleanup workspace, not from the
disposable repository root), with `HOME` and `XDG_CONFIG_HOME` set to
`/home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/isolated-home`,
`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, and `JJ_CONFIG`,
`GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, and
`GIT_ALTERNATE_OBJECT_DIRECTORIES` unset:

```sh
jj -R /home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/restore-final \
  --ignore-working-copy --at-op=f6e9450d01c4e22635b646e9038ac50980a99903124bfb7e5adc15f6a0cd878d59bf692b1032c78c83c8e49549299b02be248946281f3f58ac1328adf6ce226d \
  log -r 'main | integration | groups | present(reminders-s2) | bookmarks(glob:"night-*") | conflicts() | divergent()' ...
```

Before returning a template-parse error, jj printed this warning:

> Your repo appears to have been copied from `/home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/restore-test/.jj/repo` to `/home/hsa/projects/list_app/.jj/repo`. The corresponding repo config file has also been copied.

A second command also warned, then failed because I used invalid `heads()`
revset syntax; a third repeated the template parse failure. These are failed
checks, not evidence that restore inspection passed. I did not inspect any
config contents, retry jj, or run a live-repository command or mutation. The
warning points at the live repository path and leaves possible config-path
interaction unresolved; it is not proof that a write occurred. The supervisor
has directed that jj inspection stop while the attributable config ID/path is
checked without reading config contents.

**Minimal fix:** resolve that warning from attributable config ID/path metadata
before treating this review as a restore-validation pass or doing cleanup. If a
new read-only check is later authorized, start it from the disposable repository
root as the recovery guide prescribes (`recovery-guide.md:35-48`) and use the
pinned operation and isolated environment. Do not infer restoration success
from my failed commands.

### P2 — Proposed exact-set manifest survivor counts and arrays are stale

The selected A/B commit memberships remain usable, but the manifest's post-set
counts and survivor-head arrays were produced from the earlier 986-commit,
29-head snapshot, not recovery snapshot `f6e9450…` (report `:34-40`). In
`proposed-exact-sets.json:116-139`, A claims 19 heads/975 visible commits and
lists an old survivor set; in `:165-186`, A+B claims 17 heads/973 commits and
another stale survivor set. The recovery inventory has 988 commits and 28
heads (`current-inventory.json`; `current-heads.txt`). Applying the unchanged
members to that inventory gives:

- **A:** 11 selected exact commits, ten of them current heads (the selected
  `95b1f504…` is the parent in the two-empty tail); expected 18 heads and 977
  visible commits, not 19/975.
- **A+B:** two additional current-head leaves; expected 16 heads and 975
  visible commits, not 17/973.

I independently checked the evidence files without jj: all 11 A IDs exist in
the 988-record inventory, are empty and non-conflicted, and their archived tree
fingerprints equal their exact parents. `95b1f504…` has only the selected
`095fe95…` descendant. Both B IDs are current leaf heads with the same parent;
`31077a…` is conflicted, `d8e8f9…` is not, and neither has descendants. Thus the
selected memberships and stated A/B leaf/tree rationale remain intact, but the
stale survivor arrays cannot prove which current heads remain or support the
current-count claims.

**Minimal fix:** regenerate both count fields and complete survivor-head arrays
from the pinned `f6e9450…` inventory; retain the exact selected memberships.
Then re-review the refreshed manifest before any A/B decision. This correction
does not grant A/B approval.

## Conditional `reminders-s2` local-name gate — PASS, no action taken

The authoritative owner-follow-up permits only conditional removal after exact
main ancestry, no active name dependency, identity retention, and fresh review
(plans `jj-history-review.md:223-246`). The pinned inventory independently
confirms that local `reminders-s2` is exact commit
`e50da7ce0a5456159f8206513c820e7180abbb8e` / change
`wlwznqlymtxmxynrrwmorpvqpzmnlnly`; walking its exact parents and `main`'s
parents shows the tip is an ancestor of `main` and
`ancestors(reminders-s2) - ancestors(main)` is empty. The reference row records
that full identity and the exact inverse (cleanup report `:54`; proposed
commands, “Conditional local-name removal”):

```sh
jj bookmark forget exact:reminders-s2
jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e
```

This removes/restores a label only, not a commit or graph head. The repository
`scripts/` search found no `reminders-s2` reference; the recorded configured-jj-
alias check reports zero alias matches (`name-dependencies-config.json`), and
the task's Lead/test-peer attestation reports no known active or queued use.
The report correctly leaves owner-private aliases/external tools uncertified
(`jj-cleanup-review.md:54, 242-245, 259-261`); I did not inspect them. Its current
attention view uses `present(reminders-s2)` (`:247-250`), so the optional name
does not make that view depend on the bookmark existing. The failed disposable
command above did not execute that view successfully in this review. Treat the
local removal as conditional on the stated final coordination; this pass does
not authorize or perform it.

## Remaining classification and safety review

- **A and B remain proposals only.** Their commands are exact and individually
  bounded (`proposed-commands.md`, sections A/B). The recovery simulation's
  reported results are 28→18 heads for A, 18→16 for B, and three→two conflicts
  with both divergence pairs gone after B (`simulation-state.json` and cleanup
  report `:131-181`). No live abandon is approved. The manifest correction
  above is required first.
- **B differences are accurately described, not inferred from line counts.**
  The `31077a…` comparison includes scheduler wait/exception changes, fixture
  changes, three tests absent on that alternative, and a conflicted runtime
  guide (`pair-31077a91.diff`; report `:171-177`). For `d8e8f9…`, source/tests
  match but the retained sibling has the 74-line API guide and index link
  (`pair-d8e8f994.diff`; report `:172`). The used siblings with 135 and 143
  descendants are retained; counts overlap and are not added. The report does
  not claim equivalence from fewer lines.
- **`groups` is correctly kept as parked source.** The exact tip is identified;
  no rebase/repair is proposed. Its old migrations 15/16 collide with accepted
  migrations 15–18, so a future approved port must use new migrations after 18
  and reconcile current APIs/contracts (report `:62-78`; bounded source scout
  `groups-refs-scout.md:42-49`). The scout distinguishes earlier test receipts
  from later source/test changes.
- **Remote actions are separate and still owner-gated.** The report's
  `git ls-remote` evidence is timestamped and its five exact tips are recorded
  in `live-origin.json`. The two `--force-with-lease=<ref>:<expected-tip>`
  deletion commands at report `:87-109` are syntactically guarded proposals,
  not actions; I ran neither those commands nor any remote/dry-run command.
  Server deletion, later tracking refresh, cache-only forgetting, and
  `integration@origin` handling remain distinct. No push, fetch, or remote
  deletion is approved.
- **Recovery evidence is strong but my independent reinspection is blocked.**
  Besides the matching archive hash/size, the report and receipts describe a
  self-contained native jj/Git archive, no remotes/alternates/symlinks, 988
  metadata records, 1,024 exact trees (including conflict/divergent and old
  resume sources), and a second extraction after retirement simulation
  (`jj-cleanup-review.md:203-238`; receipts cited above). The separate trace
  result and timeout are reported accurately. I cannot elevate those existing
  receipts to a fresh successful check because of P1.
- **Budget and incidental config-copy evidence are disclosed accurately.**
  `budget-and-links.json` totals 2,693,820,416 allocated bytes against
  3,221,225,472 bytes (3 GiB), with 13,302,497,280 free against a
  6,442,450,944-byte floor; it includes the retained overnight evidence and
  the measured recovery root containing peak copies/trace. The separate
  237-byte disposable config-copy incident is acknowledged and corrected in
  the report (`:226-229`); no config contents were read here. No claim of
  always-isolated execution is warranted.
- Report links to the assignment, source scout, manifest, commands, head table,
  restore receipt, and recovery guide all resolve. `budget-and-links.json`
  also records no missing report links.

## Approval boundary and result

No app behavior or source equivalence was assessed beyond the bounded history
classification above. Exact remote-name approval, A approval, and B approval are
**not granted**. The only separately reviewed action is the conditional local
`reminders-s2` label removal, still subject to final coordination and the
uncertified private-name-use caveat. Do not run any cleanup until the P1 warning
is resolved and the P2 manifest arrays/counts are refreshed and independently
reviewed. No commit, bookmark, workspace, or remote was intentionally changed by
this reviewer.
