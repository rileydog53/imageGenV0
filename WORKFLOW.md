# Team Workflow — GitHub Issues & PRs

How the product owner, senior dev, and junior dev work together on imageGenV0.

---

## The Three Roles

| Role | Responsible For |
|------|-----------------|
| **You (Product Owner)** | Defining what to build, approving designs, testing finished work. Async, ~15 min 2–3×/week. |
| **Senior Dev (Architect)** | Breaking down tasks, reviewing code, mentoring, unblocking. |
| **Junior Dev (Builder)** | Writing code + tests, asking questions early. |
| **All** | Keeping `~/Desktop/TODO.txt` in sync; atomic commits with clear messages. |

---

## Workflow: From Roadmap to Shipped Code

### 1. Planning (Senior Dev + You)

Senior dev reads the next step in `TODO.txt` and creates a **GitHub Issue**
containing:
- **What to build** — bullet list of deliverables.
- **Design choices to resolve** — open questions for you to weigh in on.
- **Test plan** — 2–4 concrete named tests (needs approval).
- **Acceptance criteria** — all new tests pass, layout deterministic, all
  existing tests still green.
- **Related** files/steps, **Assigned to** junior, **Reviewed by** senior.

You review and approve the design choices (or flag concerns).

### 2. Design Proposal (Senior Dev)

Senior dev replies on the issue with a design proposal: resolved design
choices, the public function signature(s), return types (call out any API
surprises explicitly), and the list of files to change. You give a
thumbs-up or ask clarifying questions.

### 3. Implementation (Junior Dev)

Junior dev creates a feature branch (`git checkout -b feat/<step>`),
implements the module + tests in the established pattern (mirror the
phase's pattern file — e.g. `primitives/proteins.py`), and gets all tests
green locally:

```bash
~/Desktop/.venv/bin/pytest tests/ -v
```

### 4. Code Review (Senior Dev)

Junior dev opens a PR summarizing changes, local test results, design
decisions, and what's explicitly out of scope. Senior dev reviews for:
code quality (follows the pattern file), correctness (tests exercise key
cases, determinism holds), conventions (`ENTITY_TO_PRIMITIVE` dispatch
dicts, `LayoutEntry` namedtuple), and coverage (empty / simple / edge
cases). Junior dev addresses feedback, commits, pushes.

### 5. Simplify Pass (Junior Dev)

Run the `/simplify` skill on the changed files before merging — reviews
for reuse opportunities, quality issues, and redundancy. Commit any
resulting changes.

### 6. Merge

Squash-and-merge or merge-commit to `main` once senior dev approves.

### 7. TODO Update (Junior Dev)

Update `~/Desktop/TODO.txt`: move the step from `IN PROGRESS:` →
`COMPLETED:` (with date + commit SHA), and promote the next step into
`IN PROGRESS:`. The file lives outside the repo — no git action; just
inform the team.

---

## Commit Cadence

Three commits per step: `docs:` (README status + test count) →
`feat:` (implementation) → `test:` (tests + fixture PNGs). Easy to revert
any single layer; reads cleanly in `git log`.

---

## GitHub Issue Lifecycle

New → Approved → In Progress → Review → Closed (PR merged, TODO.txt
updated).

Useful labels: `phase-N`, `primitive`/`layout`/`render`, `junior-friendly`,
`blocked`, `review`. Optional milestones per phase show progress visually.

---

## Async Cadence

You're not always online synchronously. Issues can sit in **New** until
you approve them async; PRs get reviewed when senior dev has time (no
same-day block); you test features after a phase ships and leave feedback
in a new issue.

**Rough cadence:** one phase every 3–5 working days.

---

## Communication Tips

- **You:** review issues for clarity, approve designs before code starts,
  test finished features, flag UX issues. Don't code-review technical
  details or merge PRs yourself.
- **Senior dev:** write clear issues with acceptance criteria, propose
  designs before implementation, review PRs thoroughly, mentor (explain
  *why*). Don't code for the junior dev.
- **Junior dev:** ask questions early (in the issue, not mid-code), follow
  established patterns, write tests that pass *and* fail correctly, push
  early and often. Don't implement features outside the current issue;
  don't change the IR schema without asking.

---

## Tools

GitHub (issues, PRs, review), Terminal (running `pytest`), a text editor
or Finder (viewing rendered PNGs). That's it.
