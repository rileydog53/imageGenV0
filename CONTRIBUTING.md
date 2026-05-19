# Contributing to imageGen

This project is built by a three-role team — a product owner, a senior
architect, and a builder (often an AI agent). This file is the entry point
for anyone extending the project. For *using* imageGen, see
[README.md](README.md); for the LLM-facing interface, see [SKILL.md](SKILL.md).

## Start here

Before writing code, read in order:

1. **[ROADMAP.md](ROADMAP.md)** — phase status and what's next.
2. **[WORKFLOW.md](WORKFLOW.md)** — the three-role rhythm, GitHub issue/PR
   process, commit structure.
3. **[WORKFLOW_HABITS.md](WORKFLOW_HABITS.md)** — session start/end checklist,
   red flags, git hygiene.
4. **[DECISIONS.md](DECISIONS.md)** — cross-phase architectural decisions
   (D1–D4: IR-id tagging, watermarking, label auto-invoke, `smiles_map`).
5. **`~/Desktop/TODO.txt`** — the authoritative task list. Its `IN PROGRESS:`
   section is the current task; `COMPLETED:` has per-step history. Lives
   *outside* the repo, so it is never part of a commit.
6. **The pattern file for your phase** — e.g. `primitives/proteins.py` for a
   primitive, `layout/reaction_layout.py` for a layout engine. Copy its style.

## Per-step workflow

`scope → test plan → implement → verify → simplify → commit → TODO update`

- **Plan before code.** Even outside plan mode, propose the approach in prose
  first (signatures, helpers, test list, files touched). Get a green light.
- **Tests fail first.** A good test catches the bug it's meant to prevent.
- **Verify.** `~/Desktop/.venv/bin/pytest tests/ -v` — all green.
- **Simplify.** Run the `/simplify` review before committing.
- **Three-commit cadence per step:** `docs:` (status + test count) → `feat:`
  (implementation) → `test:` (tests + fixtures). Easy to revert any layer.
- **Update `~/Desktop/TODO.txt`** when a step completes (date + commit SHA).
- **Plan files are step-stamped and archived** — `plan-phaseN.md`, never
  overwritten.

## Hard rules

1. **No SVG strings.** Always `svgwrite` element objects.
2. **Every IR field is validated.** No raw dicts through the pipeline.
3. **Every primitive gets a golden-image test.** Visual regressions are silent.
4. **Conventions over creativity.** Copy how Nature/Cell draws it.
5. **Don't change `ir/schema.py` without explicit approval.** It is
   load-bearing.
6. **All project files live in `~/Desktop/imageGen-v0.1/`.** Throwaway
   scripts go in `~/Desktop/scratch/`.
7. **No fake data without watermarks.** Chart-of-real-measurements look →
   automatic "Illustrative" caption. No override flag.

## Code conventions

- **Future-proof every module.** Composable private helpers (`_helper_name`)
  over copy-paste. Flat namespaced style keys (`module_*`). Optional params
  default to "off". New variants extend existing helpers.
- **Decouple via protocols, not imports.** When two modules must talk, define
  the contract on a small dataclass (see `MembraneCurve.anchor_at()`).
- **Determinism matters.** Seed any randomness (NetworkX layout, etc.) with a
  fixed value.
- **Comment for the future reader.** Module docstring: visual conventions +
  future-phase coupling. Function docstring: Args, Returns, one-line
  scientific rationale. Inline comments only for non-obvious geometry. Prefer
  self-documenting names.

## Environment

- **Python:** the shared venv at `~/Desktop/.venv` (3.12). Don't create a
  project-local venv.
- **Package:** importable as `imageGen` (`pip install -e .` done); CLI is
  `python -m imageGen`.
- **Repo:** `~/Desktop/imageGen-v0.1/`, remote
  `https://github.com/rileydog53/imageGenV0` (not yet renamed).
