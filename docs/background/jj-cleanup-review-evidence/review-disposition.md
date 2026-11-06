# Review disposition

## First independent review: BLOCKED

Run `e207218b-a273-43e6-8d75-e528ccc13843`, fresh Luna/xhigh. Its raw report is
`blocked-luna-review.md`. It is failure evidence, not cleanup approval.

- P1: sandbox inspection used `-R` from live cwd with isolated HOME/config. jj
  loaded live cwd config and changed its config ID. Reviewer stopped. The Lead
  approved restoring only the exact original identifier after staging/archive
  byte comparison; mode 0600 and readback match. Original config contents were
  not inspected or edited. Only the newly created owned isolated metadata was
  removed. See `reviewer-config-id-incident.json`. The Lead accepted the repair
  receipt and allowed normal live tooling to resume.
- P2: exact-set manifest had initial-snapshot survivor arrays/counts. Memberships
  were correct, but arrays/counts are now recomputed from the actual 988-record,
  28-head recovery inventory. A leaves 18 heads/977 visible records; A+B leaves
  16 heads/975 records. No surviving commit has a removed parent. Exact owner
  approval remains absent.
- The raw report's archive checksum text contains a transcription error. Do not
  use that literal string to verify the archive. The actual checked 64-character
  SHA-256 in `recovery-receipt.json` and `restore-final-receipt.json` is
  `e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d`.
  The raw review remains unchanged as failure evidence.
- Its local-name gate assessment was favorable, but the Conductor did not act
  on a partially passed, blocked review. A fresh escalated review is required.

## Escalated review: local gate and corrections pass

Fresh static reviewer `86787486-dbdf-4ee8-8978-d160129c1218`, requested
`claude-code/claude-haiku-5-5:max`; host status confirms that provider/model and
thinking tier. Reframed boundary: no jj/Git execution at all, only file/JSON/hash
and static command review. No new archive copy. The corrected guide requires a
physical sandbox cwd before launch and rejects live pointers or alternates.

The completed static review is retained in `escalated-static-review.md`. It
independently checked the archive checksum/size/member safety, exact-set survivor
arrays, memberships, ancestry, descendant counts, budget arithmetic and report
links. It did not rerun native restore, trace, simulation or live-state checks.
It passes the conditional local-name gate after the parent's live pre-check and
final Lead coordination. A/B/remotes remain unapproved.

It found guide isolation gaps and ambiguous receipt labelling. Corrections:

- Guide now redirects XDG config/data/state/cache under isolated HOME, uses
  `python3 -I` from neutral `/tmp`, checks physical sandbox pointers/links/alternates
  before jj, sets process cwd with `env -C` before launch, and checks only names
  of live per-repo config directories before/after the first inspection. It uses
  `tar --no-same-owner`. No corrected guide command has been executed.
- `archive-refresh.json` now explicitly labels its earlier `dcbea95d` snapshot
  and points readers to the later native recovery/restore receipts.
- Current live state and repaired ID remain the parent's responsibility; neither
  reviewer independently verified them. Small later receipts need a final budget
  measurement. Narrow static follow-up `fcbe2181` passed; its raw result is
`correction-review.md`. Host completion status confirms the resumed reviewer
remained `claude-code/claude-haiku-5-5`, thinking `max`. There are no remaining
guide/label blockers. Local removal still waits for parent live checks and final
Lead coordination.

## Local action and post-action verification

After final live checks and explicit Lead no-block coordination, the Conductor
ran only `jj bookmark forget exact:reminders-s2`, exit 0. Pre/post operations are
recorded in `local-forget-command.json` and `local-forget-protected-check.json`.
The exact e50 source remains in main. All 988 visible commit records, workspace
targets, other refs, working tree and 28/3/4 head/conflict/divergence counts stayed
unchanged. Fifty-two protected exact trees include all 36 old resume commits.
Archive checksums and repaired config ID/global metadata stayed unchanged.

The standalone test copies and isolated HOME were removed after review and
process-cwd checks; durable archive/trace/methods/receipts remain. Final measured
known evidence is 1,956,982,784 allocated bytes; conservative peak bound is
2,705,956,864, below 3 GiB. Post-action static receipt review `7538d73a`
passed with no blocker; see `post-action-review.md`. Host completion status
confirms Haiku/max. The reviewer compared the actual before/after records and
cleanup/budget receipts; it did not rerun native live checks.

A/B source retirement and remote reference/server changes remain owner-gated.
