# ListR improvement delivery planning

Lifecycle: temporary

## Brief (Lead-owned)

- Outcome: prepare clear, independently reviewed plans for authorized work. Base `xvvrrzwq` f1aca0a7; destination Lead's default line. Owner explicitly authorizes integration into default without moving `integration` or `main`; no push or deploy.
- Owner decisions are in `plans/decisions-for-heming.md`; selected work in `plans/backlog.md`. Read both and project scope/architecture/instructions. Preserve all existing work and `security-small`.
- Write short **temporary** plans for: (1) preserve item capitals with case-insensitive duplicates, including data migration, conflict handling, offline/replay, compatibility and tests before implementation; (2) usual items using existing times-added count; (3) named item groups, add whole group in one tap, skip existing items; (4) ordered aisle category tags alongside person tags, store sort/group. Distinguish planned/implemented/verified and record dependency/interface risks. These four are authorized for later implementation, not in this planning batch.
- Write **tracked** assessment plans for B1 cross-room sharing without accounts, optional accounts C, and paste text with rule-based commas/newlines/leading quantities plus confirmation preview, limitations and examples. These are plan-only: no implementation. Retain option A (no cross-room sharing). No AI in app. Drop shopping-status proposal without erasing unrelated evidence.
- Ensure each plan has lifecycle line and progress at bottom; no changes to backlog/decisions (Lead owns shared agenda). Include unanswered consequential questions for Lead; prefer reasonable assumptions when owner has delegated design discretion. Do not invent approvals for security/permissions or data loss.
- Read existing code/docs and evidence enough to identify dependencies, realistic handling and tests; do not claim code implemented or verified. Independent fresh-context review of complete plan stack required. Validate links, ownership and alignment with existing scope. No feature implementation in this batch.

## Assignment

- Conductor runs in Lead-owned workspace `/home/hsa/projects/tmp-listr-planning`, agent-managed. Lead owns integration and entry cleanup. Conductor owns worker/reviewer workspaces and their cleanup, no shared backlog writes. One writer per workspace. Report to Lead via intercom.
- Bounded subagents permitted, start Luna xhigh, escalate Sol medium as required. Conductor uses GPT-6.1 Terra medium. No server/deployment/bookmarks. `.env` absent; planning needs no secrets.

## Status (Conductor-owned)

Active. Conductor will create and own child workspaces `tmp-listr-plan-features` and `tmp-listr-plan-assess`; workers will draft separate plan sets, then a fresh reviewer will assess the combined stack. Lead retains the entry workspace.

## Closeout (Conductor-owned)

Pending.
