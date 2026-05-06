# imageGenV0

Scientific figure generation skill — vector-first, IR-driven. Produces publication-style schematics, pathway diagrams, reaction schemes, and graphical abstracts from natural-language prompts.

## Status

| Phase | Description | State |
|-------|-------------|-------|
| 0 | Project setup, deps, smoke tests | ✅ Done (2026-05-02, `d82a6ce`) |
| 1 | IR schema (Pydantic models, validators, fixtures) | ✅ Done (2026-05-02, `005d794`) |
| 2 | Primitive library (arrows → proteins → membranes → …) | 🔄 Steps 1–6/7 done (`arrows.py` ✅, `proteins.py` ✅, `membranes.py` ✅, `nucleic_acids.py` ✅, `cells.py` ✅, `chemistry.py` ✅); Step 7/7: `lab_equipment.py` next |
| 3 | Layout engines | ⬜ Pending |
| 4 | Style presets | ⬜ Pending |
| 5 | Renderer & compositor | ⬜ Pending |
| 6 | Verification suite | ⬜ Pending |
| 7 | LLM frontend (`SKILL.md`) | ⬜ Pending |
| 8 | Integration & polish | ⬜ Pending |

Current test count: **127 green** (22 smoke + 25 IR + 7 arrows + 11 proteins + 12 membranes + 13 nucleic_acids + 14 cells + 23 chemistry). Phase 2 Step 7 next: `primitives/lab_equipment.py`.

## Plan

The full implementation plan lives in `~/Desktop/TODO.txt` (master) and is mirrored in `TODO.md` here. The TODO file's `IN PROGRESS:` section always reflects the current step.

## Project Conventions

- **Dev location:** `~/Desktop/imageGenV0/` (graduates to `claudeFinished/WIP/imageGenV0/` when stable).
- **Python:** uses the shared venv at `~/Desktop/.venv` (Python 3.12). Don't create a project-local venv.
- **Throwaway scripts:** go in `~/Desktop/scratch/`, never inside this repo.
- **Future-proofing:** Each primitive module uses composable private helpers (`_helper_name`), flat namespaced style keys (`module_*`), and optional params that default to "off". Phase-aware design notes in module docstrings explain how a function will couple to future modules (e.g., the `anchor_at` protocol). New variants extend existing helpers — never duplicate logic.
- **Code commenting:** Every module has a docstring explaining its visual conventions and future-phase assumptions. Every public function has a docstring with Args, Returns, and a one-line scientific rationale. Inline comments appear only for non-obvious geometry or biological conventions — not to narrate obvious code. Self-documenting variable names are preferred over comments.

## Directory Layout

```
ir/           IR schema (Pydantic models)
archetypes/   high-level figure types (pathway, reaction, workflow, etc.)
primitives/   curated visual building blocks (proteins, membranes, arrows…)
layout/       per-archetype layout engines + label placement
styles/       journal-style presets (cell_press, nature, acs)
render/       compositor, exporters, CLI
verify/       semantic / legibility / convention checks
references/   conventions notes
tests/        pytest suite + golden-image regressions
```

## Workflow

Each step follows: scope → test plan → implement → verify → commit → TODO update. New chats can pick up by reading `~/Desktop/TODO.txt` and looking at `IN PROGRESS:`.
