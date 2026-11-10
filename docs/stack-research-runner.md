# Overnight stack research

Run `scripts/stack_research.py` in a terminal. It runs only the six Phase 1
research tasks in `lr-zja`, then stops before the owner decision `lr-25k`.
Starting the script starts the approved research. It does not approve a rewrite.
Preparation checks are in the [verification record](background/stack-research-runner-checks.md).

## Start and control

From the runner workspace, in Fish or Bash:

```sh
uv run python scripts/stack_research.py plan
uv run python scripts/stack_research.py start
```

Keep that terminal and the computer running. Do not add `&`, `nohup`, or a time
limit. Each agent runs under the foreground runner. The runner uses Pi's JSON
mode, not an interactive agent chat. Only one runner can run at a time.

In another terminal, from the same workspace:

```sh
uv run python scripts/stack_research.py status
uv run python scripts/stack_research.py stop
```

Ctrl+C in the runner terminal also stops it. A stop ends the active agent process
group. Partial logs remain, but the active response might be incomplete. Finished
reports remain. No later task starts. An update already sent to Beads can finish;
a stop does not undo it. Claims remain with their recorded owner.

After inspecting an interrupted run:

```sh
uv run python scripts/stack_research.py resume --retry-partial
```

This preserves interrupted-stage files and starts that stage again with fresh
context. Verified finished stages are reused. Plain `resume` refuses to replay
an interrupted stage. Ownership changes, invalid reports and review failures
need inspection; resume does not override them. Do not delete state or force a
claim to make the run continue.

## Results and limits

The default private result folder is:
`~/.local/share/list-app-stack-research/phase-one/`.

- `state.json`: progress, exact baseline, sessions and workspace ownership.
- `<bead>.md`: finished research report; `<bead>.json`: summary and limitations.
- Stage folders: prompts, Pi sessions, event logs, errors and completion receipts.
- `interrupted/`: preserved attempts from an explicit retry.

Use `--run-dir PATH` on every command to select a different result folder.
A new folder does not bypass existing claims or workspace-name collisions.

Owners use **Sol 6.1/high**. Bounded workers and fresh reviewers use
**Luna 6/xhigh**. An incomplete worker result or a second fresh review uses
**Terra 6.1/low**. All are OpenAI models. There is no runtime or spend limit.
Workers are sequential script-managed sessions, not recursive agent fan-out.
There is one repair pass after review; unresolved findings stop the queue.

Agents can read an explicit list of tracked text sources and research reports,
and research the web. A run-local Pi guard blocks other file reads, directory
searches, shell commands, file writes, browser automation, MCP and delegation.
Web retrieval is limited to unauthenticated HTTPS text; local-file fetches and
video-model calls are blocked. Search uses OpenAI and rejects obvious code or
private-path payloads. Generic search queries still require agent judgment;
this is not an OS sandbox or a complete data-loss prevention system.

The script alone manages workspaces, reports, claims and guarded closures. It
verifies the actual model, reasoning, guard startup, final response and
fresh-review verdict before closure. Each source-reading session must first run
the loaded runtime doctor. The guard allows only that diagnostic subagent action;
it blocks agent launches. Fresh no-tools canaries check all three model tiers. Status checks the runner lock, not only
saved progress. Resume refuses to start if a retained Pi session is still live.

Each task reads its own clean jj workspace at the same accepted baseline, fixed
at run start. Reports stay outside the repo. Workspaces are retained for review;
they need no `.env`. No app code, bookmarks, dependencies or production data are
changed. Beads data is synced to its configured remote. No code is pushed.

A completed Pi response can leave extensions running. After the explicit
`agent_settled` event, the runner gives Pi two seconds to exit, then ends that
owned process group. This does not limit research time.
