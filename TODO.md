# TODO (mirror)

The authoritative TODO lives at `~/Desktop/TODO.txt`. That file is the single source of truth for project state.

**To find the current step:** open `~/Desktop/TODO.txt` and read the `IN PROGRESS:` section. If it's empty, the next step comes from `PENDING:`.

**Workflow per step:**

1. Scope — restate the step, flag ambiguity. No code yet.
2. Test plan — propose 2–4 concrete tests; user approves.
3. Implement — code + tests in one diff.
4. Verify — run pytest, show output.
5. Commit — atomic, descriptive message.
6. TODO update — move step from `IN PROGRESS:` → `COMPLETED:` (with date + commit SHA), promote next step into `IN PROGRESS:`.
7. Decide: continue this chat or start a new one (default: new chat at every phase boundary).

This file exists so new contributors / fresh chats see the workflow without needing to scroll the master TODO.
