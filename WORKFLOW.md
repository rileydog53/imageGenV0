# Team Workflow — GitHub Issues & PRs

This document explains how your junior dev, senior dev, and you work together on imageGenV0.

---

## The Three Roles

| Role | Responsible For | Time Commitment |
|------|-----------------|-----------------|
| **You (Product Owner)** | Defining what to build, approving designs, testing finished work | Async, ~15 min 2–3x/week |
| **Senior Dev (Architect)** | Breaking down tasks, reviewing code, mentoring junior, unblocking | ~10–15 hours/week |
| **Junior Dev (Builder)** | Writing code, writing tests, asking questions early | Full-time (or project-time) |
| **All** | Keeping `~/Desktop/TODO.txt` in sync, atomic commits with clear messages | ~5 min per completion |

---

## Workflow: From Roadmap to Shipped Code

### Phase 0: Planning (Senior Dev + You) — 30 min

**Location:** GitHub issue

Senior dev reads the next step in `TODO.txt` and creates a **GitHub Issue** with:

```markdown
## Phase 3, Step 2: layout/pathway_layout.py

**What to build:**
- Group entities by compartment
- Render compartments as horizontal bands
- Use NetworkX graph layout + constrain to band bounds
- Route arrows to avoid crossings
- Hand off to label_placement for text placement

**Design choices to resolve:**
- Compartment ordering: hardcode or read from Figure?
- Primitive selection: dispatch dict or entity.style?
- Arrow routing: simple curves or force-directed?

**Test plan (needs approval):**
1. test_pathway_layout_empty_figure — single entity, no compartments
2. test_pathway_layout_mapk_cascade — 5 entities, 3 compartments, 4 relations
3. test_pathway_layout_cross_compartment_arrows — relations crossing compartment boundaries
4. test_pathway_layout_isolated_entities — entities with no relations

**Acceptance criteria:**
- All 4 tests pass ✅
- Layout is deterministic (same IR → same positions) ✅
- No overlapping arrows ✅
- All 172 existing tests still pass ✅

**Related:** Phase 3 Step 1 (reaction_layout.py), ir/schema.py

**Assigned to:** @junior-dev
**Reviewed by:** @senior-dev
```

**You review and approve the design choices** (or flag if something seems off).

---

### Phase 1: Design Proposal (Senior Dev) — 15 min

Senior dev replies with a **design proposal:**

```markdown
## Design Proposal

Based on the fixtures and existing patterns, I propose:

**Compartment ordering:** Read from Figure.compartments order (consistent with reaction_layout's entity ordering). If missing, default to extracellular → cytoplasm → nucleus (biological convention).

**Primitive selection:** Dispatch dict in pathway_layout module. Example:
```python
ENTITY_TO_PRIMITIVE = {
    EntityType.PROTEIN: lambda label, pos, style: proteins.generic_protein(...),
    EntityType.KINASE: lambda label, pos, style: proteins.kinase(...),
    # etc.
}
```

**Arrow routing:** Start simple (curve arrows that would cross), upgrade post-v1. Seed NetworkX RNG for determinism.

**Return type:** Reuse LayoutEntry from reaction_layout. Import it; move to layout/__init__.py later when shared widely.

### Public function signature:
```python
def layout_pathway(figure: Figure, layout_params: dict, style_dict: dict) -> list[LayoutEntry]:
    """Group entities by compartment, layout via NetworkX, route arrows, return LayoutEntry list."""
```

### Files to change:
1. `layout/pathway_layout.py` — new file, ~200 LOC
2. `tests/test_layout_pathway.py` — new file, ~200 LOC
3. `tests/fixtures/pathway_*.json` — already exist, use for fixtures
4. `tests/figures/pathway_*.png` — will generate golden images in Phase 6
5. `README.md` — bump test count from 172 → ~192

**Does this direction work?**
```

**You give a thumbs-up** (or ask clarifying questions).

---

### Phase 2: Implementation (Junior Dev) — 4–6 hours

Junior dev creates a **feature branch:**

```bash
git checkout -b feat/pathway-layout
```

Implements `layout/pathway_layout.py` + tests:

```python
def layout_pathway(figure: Figure, layout_params: dict, style_dict: dict) -> list[LayoutEntry]:
    """
    Layout entities grouped by compartment, using constrained graph layout.
    
    Returns list of LayoutEntry(primitive_func, args, kwargs, position).
    """
    # 1. Validate input
    # 2. Group entities by compartment
    # 3. Render compartment bands
    # 4. Run NetworkX layout within each band
    # 5. Route arrows
    # 6. Return LayoutEntry list
```

Writes tests following the pattern in `test_primitives_proteins.py`:

```python
def test_pathway_layout_empty_figure():
    """Single entity, no compartments."""
    ...

def test_pathway_layout_mapk_cascade():
    """5 entities, 3 compartments, 4 relations."""
    ...

# etc.
```

Runs locally:

```bash
~/Desktop/.venv/bin/pytest tests/test_layout_pathway.py -v
```

Gets all 4 tests green.

---

### Phase 3: Code Review (Senior Dev) — 30–45 min

Junior dev opens a **GitHub Pull Request:**

```markdown
## [Phase 3.2] Implement pathway_layout.py

Compartment-aware layout for biological pathways.

**Changes:**
- layout/pathway_layout.py — 210 LOC, full implementation
- tests/test_layout_pathway.py — 200 LOC, 4 test cases
- README.md — bump test count to 192

**Tested locally:**
- `pytest tests/test_layout_pathway.py -v` — 4/4 green ✅
- `pytest tests/ -v` — 176/176 green (172 existing + 4 new) ✅
- Fixtures used: pathway_mapk.json, pathway_ecm_signaling.json

**Design decisions:**
- Compartment ordering: read from Figure.compartments (else default bio convention)
- Primitive selection: ENTITY_TO_PRIMITIVE dispatch dict
- Arrow routing: simple curve-to-avoid v1, documented for upgrade

**Not in this PR (Phase 3.3+):**
- Label placement (deferred to Phase 3.4)
- Panel layout (deferred to Phase 3.3)
```

**Senior dev reviews:**

1. **Code quality:** Does it follow the pattern from reaction_layout.py? Is it testable?
2. **Correctness:** Do the tests exercise the key cases? Do determinism guarantees hold?
3. **Conventions:** Does it use the established style (ENTITY_TO_PRIMITIVE dict, LayoutEntry namedtuple)?
4. **Coverage:** Do the 4 tests cover empty, simple, cross-compartment, and isolated cases?

Comments:

```markdown
### Code Review Feedback

Line 45: `spring_layout` should use a pinned seed for determinism:
```python
pos = nx.spring_layout(G, seed=42, **layout_params)
```

Line 78: Consider renaming `_route_arrow` to `_curve_arrow_if_crossing` — more descriptive.

Otherwise LGTM! Small tweaks and we're good.
```

Junior dev makes the requested changes locally, commits, and pushes:

```bash
git add layout/pathway_layout.py tests/test_layout_pathway.py
git commit -m "fix: pin seed in spring_layout for determinism, rename arrow routing helper"
git push origin feat/pathway-layout
```

Senior dev approves the PR: ✅ **Approved**

---

### Phase 4: Simplify Pass (Junior Dev) — 10 min

Junior dev runs the `/simplify` skill on the changed files locally before merging:

The skill reviews the code for:
- Reuse opportunities (consolidate similar logic)
- Quality issues (inefficient loops, confusing patterns)
- Redundancy (functions that could collapse)

Updates if needed, commits again.

---

### Phase 5: Merge (Senior Dev or Junior Dev) — 2 min

Senior dev merges the PR to `main`:

```bash
# On GitHub PR page:
[Squash and merge] or [Create a merge commit]
Commit message: "feat(layout): implement pathway_layout.py — Phase 3 Step 2"
```

Or junior dev merges (on senior dev's go-ahead):

```bash
git checkout main
git merge feat/pathway-layout
git push origin main
```

---

### Phase 6: TODO Update (Junior Dev) — 5 min

Update `~/Desktop/TODO.txt`:

1. **Remove from `IN PROGRESS:`**

```markdown
# OLD IN PROGRESS:
## Phase 3 — Step 2: layout/pathway_layout.py
...
```

2. **Add to `COMPLETED:`** with date + commit SHA

```markdown
## Phase 3 — Step 2: layout/pathway_layout.py — DONE (2026-05-10, commit abc1234)
Compartment-aware layout for biological pathways. 4 tests, deterministic graph layout, arrow routing.
- 172 → 176 total green tests
```

3. **Promote next step to `IN PROGRESS:`**

```markdown
## Phase 3 — Step 3: layout/panel_layout.py ← NEXT UP
...
```

Push the TODO update (it lives outside the repo, in `~/Desktop/TODO.txt`):

```bash
# No git action needed — this file is external. Just inform the team:
# "TODO.txt updated. Phase 3.3 is now in progress."
```

---

## GitHub Issue Management

### Issue Lifecycle

1. **New** — Created by senior dev, awaiting approval from you
2. **Approved** — You've signed off on the design
3. **In Progress** — Junior dev is working (assign to junior dev)
4. **Review** — PR is open, senior dev is reviewing
5. **Closed** — PR merged, `TODO.txt` updated

### Labels (Recommended)

- `phase-1` / `phase-2` / etc. — which phase
- `primitive` / `layout` / `render` — which module type
- `junior-friendly` — good first task
- `blocked` — waiting on something else
- `review` — code review needed

### Milestones (Optional but Useful)

Create milestones for each phase:

- **Phase 3 (Layout Engines)** — 4 issues (reaction_layout ✅, pathway_layout, panel_layout, label_placement)
- **Phase 4 (Style Presets)** — 1 issue
- etc.

Shows progress visually: "Phase 3: 2/4 complete" 📊

---

## Communication Tips

### What You Should Do (Product Owner)

- ✅ Review GitHub issues for clarity (ask clarifying questions)
- ✅ Approve design proposals before code starts
- ✅ Test finished features (click buttons, verify output)
- ✅ Provide feedback in PRs (you might spot UX issues devs miss)
- ❌ Don't code-review technical details (that's the senior dev's job)
- ❌ Don't merge PRs yourself (senior dev decides when it's ready)

### What Senior Dev Should Do

- ✅ Create GitHub issues with clear acceptance criteria
- ✅ Propose designs before implementation
- ✅ Review PRs thoroughly (code quality, tests, conventions)
- ✅ Mentor the junior dev (explain *why*, not just *what*)
- ✅ Unblock the junior dev (help debug, suggest patterns)
- ❌ Don't code for the junior dev (let them struggle productively)

### What Junior Dev Should Do

- ✅ Ask questions early (in the issue, not halfway through code)
- ✅ Follow the established patterns (check Phase 2's proteins.py before writing Phase 2.5)
- ✅ Write tests that pass *and* fail correctly (a good test catches the bug it's meant to catch)
- ✅ Push early and often (so senior dev can see progress)
- ✅ Read error messages carefully (pytest output is your friend)
- ❌ Don't implement features not in the current issue
- ❌ Don't change the IR schema without asking

---

## Async Workflow (What If You're Not All Online?)

Since you're not a coder, you might not always be available synchronously. Here's how to handle that:

### Senior Dev Creates Issue (Morning) → You Approve (Afternoon)

Issue sits in **New** status. Senior dev drafts a design proposal comment. You read it that afternoon, leave a thumbs-up or questions. Next morning, if approved, senior dev writes the acceptance criteria.

### Junior Dev Implements (Day 2) → Senior Dev Reviews (Day 3) → Merges (Day 4)

Junior dev opens a PR. Senior dev reviews when they have time (doesn't block same-day). Once approved, junior dev merges. No waiting on you.

### You Test (Post-Merge) → Provide Feedback (2–3 Days Later)

After a phase ships, you test the feature (click buttons, verify it does what you wanted). Leave feedback in a new issue or a separate GitHub Discussions post. Senior dev and junior dev read and incorporate into the next phase.

**Cadence:** One phase every 3–5 working days (Phase 2 took ~5 days for 7 primitives; Phase 3 will take ~6 days for 4 layout engines).

---

## Example: Weekly Standup (Optional, but Helpful)

If you all sync once a week (30 min):

**Agenda:**

1. **What shipped this week?** (2 min) — Junior dev: "Phase 3.1 is done, 4 tests pass"
2. **What's the blocker?** (3 min) — Junior dev: "I'm confused about how to handle cycles in the relation graph"
3. **What's next?** (2 min) — Senior dev: "This week we're starting Phase 3.2 (pathway layout). I'll write the issue by EOD."
4. **Feedback from Joey?** (3 min) — You: "The Phase 2 chemistry output looks great. One thing: the label colors are a bit faint on dark backgrounds — let's boost contrast in Phase 4."

**Outcome:** Clear direction, quick unblocks, shared understanding.

---

## Tools You'll Need

- **GitHub** — issues, PRs, code review
- **Terminal** (on your Mac) — running `pytest` to verify locally
- **A text editor or Finder** — viewing rendered PNGs to test visually

That's it. You don't need Jira, Slack bots, or other tools (unless you want them later).

---

## Summary: The Three-Role Rhythm

```
Day 1 (Morning):   Senior dev writes GitHub issue + design proposal
Day 1 (Afternoon): You approve
Day 2–3:           Junior dev implements + writes tests locally
Day 3 (EOD):       Junior dev opens PR
Day 4 (Morning):   Senior dev reviews, requests changes
Day 4 (Afternoon): Junior dev updates, senior dev approves
Day 4 (EOD):       Junior dev merges + updates TODO.txt
Day 5:             Phase ships, you test when you get a chance

Next phase starts Day 6.
```

---

## Questions?

If any of this is unclear, ask before starting! The workflow is there to help, not hurt.
