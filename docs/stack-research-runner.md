# Overnight stack research

Run `scripts/stack_research.py` from a Zellij terminal. It runs only the six
Phase 1 tasks in `lr-zja`, then stops before the owner decision `lr-25k`.
Starting it starts the approved research. It does not approve a rewrite.
Preparation checks are in the [verification record](background/stack-research-runner-checks.md).

## Start

From the runner workspace, in Fish or Bash:

```sh
uv run python scripts/stack_research.py plan
uv run python scripts/stack_research.py start
```

Keep the runner terminal and computer awake. Do not add `&`, `nohup`, or a time
limit. There is no runtime or spend cap. Only one runner can run at a time.

## Talk to an agent or stop

Each agent opens as **interactive Pi in its own Zellij tab**, named
`list-<stage>`. The runner prints its tab and pane IDs. New tabs do not take
focus. Switch to the agent tab to see its work or talk to it.

**Only one runner-managed Pi agent runs at a time**, including workers and
reviewers. On completion, the runner saves the result, exits Pi back to Fish,
and closes its owned pane and empty tab before opening the next one. It does
not close other user panes. Finished chats remain in the saved session files.

Type **`stop`** in the active Pi pane to stop the whole queue. The guard handles
this directly, without waiting for the model to decide. `please stop`, `pause`,
`abort`, and `cancel` also work at the start of a message. Interrupting the Pi
run with Escape, or closing its pane, also prevents the queue from continuing.
Normal questions go to Pi; a final answer that is not a valid research result
stops the queue rather than being mistaken for completion.

You can also press Ctrl+C in the runner terminal, or use another terminal in
the same workspace:

```sh
uv run python scripts/stack_research.py status
uv run python scripts/stack_research.py stop
```

Stopping preserves completed reports and partial logs. The active response may
be incomplete. An update already sent to Beads can finish; stop does not undo
it. Claims remain with their recorded owner. No later task starts.

## Results and recovery

Default private result folder:
`~/.local/share/list-app-stack-research/phase-one/`.

- `state.json`: progress, baseline, session and active pane IDs.
- `<bead>.md` and `<bead>.json`: finished report, summary and limitations.
- Stage folders: prompts, sessions, event logs, terminal snapshots, pane
  ownership, readiness and review evidence.
- `interrupted/`: preserved attempts from an explicit retry.

After inspecting an interrupted run:

```sh
uv run python scripts/stack_research.py resume --retry-partial
```

This preserves interrupted files and restarts that stage in a fresh pane.
Verified finished stages are reused. Plain `resume` refuses to replay an
interrupted stage. A retained live pane/session, changed ownership, invalid
report or failed review needs inspection; resume does not override it.
Use `--run-dir PATH` on every command to select a different result folder.

## Models and boundaries

Owners use **Sol 6.1/high**. Every reviewer, including a fresh second review,
uses **Sol 6.1/low**. Bounded evidence workers use **Luna 6/xhigh**; an incomplete
worker result can be retried with **Terra 6.1/low**. All are OpenAI models.
There is one repair pass after review; unresolved findings stop the queue.
Agents cannot launch other agents.

Each task reads its own clean jj workspace at the same accepted baseline,
fixed at run start. Reports and workspaces remain for owner review. No `.env`
is needed. No app code, bookmarks, dependencies or production data are changed.
Only Beads data is synced; no code is pushed by the runner.

The run-local guard permits only listed text sources and research reports.
It blocks shell commands, writes, directory searches, browser automation and
MCP. Web retrieval is unauthenticated HTTPS text; queries use OpenAI and reject
obvious code/private-path payloads. Query content still needs agent judgment;
this is not an OS sandbox or a complete data-loss prevention system.

Before dispatch, the runner verifies the live Pi session, TUI mode, model,
reasoning, directory and pane through a two-way file handshake. Each source
reader must pass the loaded runtime doctor; no other subagent action is allowed.
Fresh no-tools canaries check all four model/reasoning combinations. A bead closes only after
valid completion evidence and an independent review.
