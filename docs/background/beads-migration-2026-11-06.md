# Beads migration evidence — 2026-11-06

## Result

The unfinished Markdown queue was migrated to the local native Beads store at
`/home/hsa/projects/list_app/.beads`. The shared backlog is now a pointer, not a
second live queue. Operational instructions are in [the Beads guide](../beads.md).

The accepted setup is change `nzqrxmnn`, commit
`a45a9701a29e496bcdee609aa75cea8ebdb8c695`. Its parent is the Lead's exact backlog
pointer change `lqkpwtsv`, commit
`27e2a4bb003cae97aa8ee9009edb18e7883013a5`. The five setup files were unchanged
by the mechanical rebase onto that pointer. No bookmarks moved for this work.

## Scope and source preservation

- All 32 queue entries were imported in source order, with their full source
  excerpts and metadata. All priorities are P2.
- Source groups remain recorded: 4 In progress, 1 Blocked, 8 Later and 19 Ideas.
  They are not active delivery claims. Native state is 31 deferred and one
  blocked, with zero ready or in-progress tasks.
- No assignees, owners, leases, parents or dependency edges were introduced.
  `lr-005` retains its explicit red browser-verification gate.
- The 34 original source snapshots, 27 attached source documents and 21 incoming
  named backlog links were checked. Plans remain supporting detail, not extra
  imported tasks. The original source baseline is `6d4b0dcba76c3dcba2615f84656a3a954bf075fc`.
- Category/aisle-tag uncertainty remains unresolved on `lr-027`. The
  `lr-002`/`lr-026` overlap remains explicit and unmerged. The S3 scope decision
  is not implementation approval. S5 retains its S4 **or** in-app-only S3
  condition; no false unconditional edge was added.

Native export omits 128 empty-string or empty-array fields and adds native type
and count fields. Complete field and metadata comparisons found no other
import differences. This administrative normalization does not change source
wording or task scope.

## Native recovery and independent checks

Preparation used a private store outside Git. A native backup was restored into
an independently initialized, empty disposable store. The Lead then activated
the complete native store, root gate and companions in the primary workspace.
No JSONL-only restore was used.

After activation, the Lead created a new canonical native backup at
`/home/hsa/.local/share/beads-backups/list_app/canonical-native-20261106` and a
new isolated restore. The operational native backup at
`/home/hsa/.local/share/beads-backups/list_app/native` was resynchronized.

Full comparisons covered 139 outputs per store: all 32 records and metadata,
all 32 unlimited issue histories, audit-event histories and provenance queries,
the journal, the full 77-entry Dolt log, branches, working status and all 32
native tables/views. They matched the frozen preparation evidence and each
other. The records include 96 audit events and 64 labels, with no dependency
or lease rows. Journal and provenance were empty; this does not test their
recovery with nonempty data.

A fresh command-capable `openai/gpt-6-luna:xhigh` reviewer checked the combined
setup and actual pointer. Its initial raw BLOCK was retained: an oversized
summary caused automatic tool-output retention under the private `TMPDIR`.
The Lead checked the exact file and private ancestry and accepted it as protected
harness output, not an actual safety failure. The same fresh-origin reviewer
then resumed and returned a focused PASS for the remaining checks. The raw
BLOCK was not relabeled. Its Dolt table/log findings use complete writer-only
recorded queries; the reviewer did not run standalone Dolt.

After the Lead's canonical recovery passed, the Conductor independently checked
canonical `where`, the full export, settings, metrics, remotes and all six
reviewed setup/pointer file hashes. The canonical records matched the frozen
records and metadata. All 139 captured outputs per store were also compared
against the frozen captures, with no mismatch. These direct checks used
explicit paths, sandbox and read-only mode, with an owned-path audit after each
native command. No standalone Dolt was run for this final check.

## Privacy and limits

Metrics are off. Local-only mode is on. Automatic push, backup, export and Git
staging are off; task remotes are empty. Native metadata mode failures and
authorized corrections remain recorded. Corrections preserved content hashes;
final owned directories were mode `700` and files mode `600`. The shared backup
parent was left unchanged. These checks do not establish broader containment.

Recovery is verified on this machine only, not against machine loss. Normal
read-only engine metadata effects are not task-content changes; physical
mutable engine-file byte identity was not an acceptance gate. No application
code changed. App suites, documentation preview, services and deployment were
not run.

## Protected evidence

These are local evidence paths, not published artifacts:

- Runtime: `/home/hsa/.local/share/beads-migration-runtimes/list_app/runtime`.
  `frozen/final-handoff.json` binds the source snapshots, complete native
  archives, gates, raw records, terminal children and combined review. Its SHA-256
  is `136b169d9cd3e772cd14420ed399f1c2149d8447af8060e4100b1ac19b570a1b`.
- The same runtime retains `final-independent-review.initial-block.md`,
  `final-independent-review.continuation.md` and the Lead's exact protected-output
  audit disposition. `canonical-independent-check.json` records the direct
  canonical check; its SHA-256 is
  `e72da7f0d3b970bd44884f393cd354314990208e6ff0b53030d1486abd007bf3`.
- Canonical activation/recovery proof and raw captures:
  `/home/hsa/.local/share/beads-backups/list_app/lead-activation-20261106/verification.json`.
- Preparation has 318 actual numbered direct commands. An earlier count of 319
  included an embedded prior index object, not another native command. The raw
  index remains unchanged; exact numbered records are the command mapping.
