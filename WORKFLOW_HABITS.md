# Workflow Habits — imageGenV0

Cheat sheet for sustainable session-to-session development.
Read this at the start of any session where you're not sure what state you're in.

---

## Session Start (2 min)

1. Read the `IN PROGRESS:` block in `~/Desktop/TODO.txt`
2. Run `pytest tests/ -v` — confirm green count matches what TODO.txt says
3. Check that the file described in IN PROGRESS actually exists with real content
4. If count or file doesn't match → fix `IN PROGRESS` before doing anything else

## Session End (2 min)

1. Rewrite `IN PROGRESS:` for the *next* step before closing the chat
2. Confirm all three commits are done: `docs:` → `feat:` → `test:`
3. Add any new "out of scope" decisions to `BACKLOG.md` as a new row
4. Update the test count in `README.md`'s status table

---

## When to Pause vs. Push

Stop and consolidate when any of these are true:

| Signal | Action |
|---|---|
| `BACKLOG.md` Cleanup bucket has 3+ High items | Do a cleanup commit before starting the next phase |
| You've just finished a phase | Don't start the next one — do one cleanup pass on the C-bucket first |
| A session ended mid-step | Verify state and re-scope before continuing |

**Cleanup status:** C1/C2/C3 were resolved in the pre–Phase 5 cleanup
(2026-05-11). C4/C5 remain (Low/Medium) — see `BACKLOG.md`.

---

## Cross-Chat Continuity

Your main anchors: `TODO.txt IN PROGRESS` + `BACKLOG.md` + three-commit cadence.

**Gap to watch:** design choices resolved during planning disappear after the chat.
Fix: when a design question is answered, add a one-liner to the step's COMPLETED entry
in `TODO.txt` before closing. See also `DECISIONS.md` (repo root) for cross-phase
architectural choices.

**Definition of "step complete":**
All acceptance-criteria tests pass, `/simplify` has run, three commits are on `main`,
`IN PROGRESS` is rewritten for the next step, and `BACKLOG.md` has any new deferrals.

---

## Git Hygiene

| What | When | Command |
|---|---|---|
| Push to GitHub | End of every phase | `git push origin main` |
| Tag the phase | End of every phase | `git tag phase-N-complete <hash>` |
| Feature branch | Step spans 2+ sessions or involves risky refactors | `git checkout -b phase5-compositor` |
| Push before starting a new phase | Always — disk-failure insurance | `git push origin main` |

**Rule:** tag + push at every phase boundary. Never go more than one phase without pushing.

---

## Red Flags

| Red flag | What to do |
|---|---|
| `pytest` count ≠ README / TODO.txt count | Stop. Fix the count before writing new code. |
| BACKLOG C-bucket has 5+ High items | Do a cleanup pass — this will block Phase 6 |
| `IN PROGRESS` describes a file that already exists with content | TODO.txt is stale — update it first |
| Same step spans 3+ sessions | Split the step |
| >3 unresolved design questions before coding starts | Resolve them in the planning chat, not mid-implementation |
| `feat:` commit with no accompanying `test:` commit | Red line — every feature needs tests in the same step |

---

## Graduation Signals

### `imageGenV0/` → `claudeFinished/WIP/imageGenV0/`
- Phase 7 (LLM frontend / `SKILL.md`) is complete
- Skill accepts a natural-language prompt and returns a valid SVG
- Tests pass, golden images exist, `SKILL.md` is written
- *Don't move it just because the renderer works — it needs a real entry point*

### `claudeFinished/WIP/` → `claudeFinished/apps/`
- Phase 8 (integration & polish) done
- You've personally used it to generate ≥3 real figures for coursework or papers
- No open High-priority `BACKLOG.md` items remain
- *"Shipped" means you'd give someone else the path without warning them*

**Also do when graduating:** rename `imageGenV0` → `imageGen`, update `CLAUDE.md`'s
project table, push a `v1.0` tag.

---

## Biggest Current Exposure

Push cadence: tag + push at every phase boundary — a disk failure between
pushes loses everything since the last one.
