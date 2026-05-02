# imageGenV0

Scientific figure generation skill — vector-first, IR-driven. Produces publication-style schematics, pathway diagrams, reaction schemes, and graphical abstracts from natural-language prompts.

## Status

Phase 0 — scaffolded, no implementation yet.

## Plan

The full implementation plan lives in `~/Desktop/TODO.txt` (master) and is mirrored in `TODO.md` here. The TODO file's `IN PROGRESS:` section always reflects the current step.

## Project Conventions

- **Dev location:** `~/Desktop/imageGenV0/` (graduates to `claudeFinished/WIP/imageGenV0/` when stable).
- **Python:** uses the shared venv at `~/Desktop/.venv` (Python 3.12). Don't create a project-local venv.
- **Throwaway scripts:** go in `~/Desktop/scratch/`, never inside this repo.

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
