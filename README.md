# imageGenV0

Scientific figure generation skill — vector-first, IR-driven. Produces publication-style schematics, pathway diagrams, reaction schemes, and graphical abstracts from natural-language prompts.

---

## 🤖 For AI Agents: Start Here

You're working as the **builder** in a 3-role team (you, a senior architect, and a product owner). Before writing code:

1. **[ROADMAP.md](ROADMAP.md)** (5 min) — Current phase/step, what's done, what's next, test count
2. **[WORKFLOW.md](WORKFLOW.md)** (10 min) — The 3-role rhythm, GitHub PR process, how to structure your commits
3. **[WORKFLOW_HABITS.md](WORKFLOW_HABITS.md)** (3 min) — Session start/end checklist, red flags, git hygiene, graduation signals
4. **[DECISIONS.md](DECISIONS.md)** (3 min) — Architectural decisions that span phases. Read if your task touches any cross-cutting concern (IR-id tagging, watermarking, SMILES, labels).
5. **`~/Desktop/TODO.txt`** `IN PROGRESS:` section — Your specific current task with acceptance criteria
6. **Pattern file** — Read the completed module matching your phase (e.g., `primitives/proteins.py` for Phase 2 style)

### Quick Context

- **Phase:** 5 (Renderer/compositor) — Step 3 done, Step 4 next (`render/export.py` PNG/PDF)
- **Tests:** 304 passing ✅
- **Next task:** See `~/Desktop/TODO.txt` IN PROGRESS — Phase 5 Step 4 export.py
- **Venv:** `~/Desktop/.venv` (Python 3.12, auto-activated in Terminal)
- **Key files:** `ir/schema.py` (don't change), `layout/reaction_layout.py` (pattern to follow), `tests/fixtures/` (example IRs)

### TL;DR for the Impatient

Read the **IN PROGRESS section** of `~/Desktop/TODO.txt`. It tells you:
- What to build (in plain English)
- Acceptance criteria (tests that must pass)
- Design choices to make
- Where to look for patterns

Then follow the step workflow: **Scope → Test plan → Implement → Verify → Simplify → Commit → Update TODO.txt**.

---

## Status

| Phase | Description | State |
|-------|-------------|-------|
| 0 | Project setup, deps, smoke tests | ✅ Done (2026-05-02, `d82a6ce`) |
| 1 | IR schema (Pydantic models, validators, fixtures) | ✅ Done (2026-05-02, `005d794`) |
| 2 | Primitive library (arrows → proteins → membranes → …) | ✅ Done (2026-05-06, all 7 modules complete: arrows, proteins, membranes, nucleic_acids, cells, chemistry, lab_equipment) |
| 3 | Layout engines | ✅ Done (2026-05-10, all 4 steps: `reaction_layout.py`, `pathway_layout.py`, `panel_layout.py`, `label_placement.py`) |
| 4 | Style presets | ✅ Done (2026-05-10, three JSON presets + Pydantic-validated `loader.py`) |
| 5 | Renderer & compositor | 🔄 In progress (Steps 1–3 done: PATHWAY + REACTION_SCHEME + PANEL in `compositor.py`) |
| 6 | Verification suite | ⬜ Pending |
| 7 | LLM frontend (`SKILL.md`) | ⬜ Pending |
| 8 | Integration & polish | ⬜ Pending |

Current test count: **304 green** (22 smoke + 25 IR + 7 arrows + 11 proteins + 12 membranes + 13 nucleic_acids + 14 cells + 23 chemistry + 29 lab_equipment + 16 layout_reaction + 30 layout_pathway + 16 layout_panel + 16 layout_label_placement + 25 styles_loader + 41 render_compositor). Phase 2 (primitive library) complete. Phase 3 (layout engines) complete. Phase 4 (style presets) complete. Phase 5 Steps 1–3 complete: `render/compositor.py` dispatches PATHWAY, REACTION_SCHEME, and multi-panel figures; IR-id tagging (D1) with panel-chain scoping (`p1__ras`); per-panel label auto-invoke (D3); watermark stub (D2); `smiles_map` threading per D4. `LayoutEntry` gains `panel_chain: tuple[str, ...]` field (backward-compatible default `()`). `_label_requests_fn` now covers all pathway-family archetypes.

**Pre–Phase 5 cleanup (2026-05-11):** `LayoutEntry` lives in `layout/types.py` (re-exported from `layout`); `ENTITY_BBOX` and `ENTITY_TO_PRIMITIVE` live in `layout/_geom.py`; test helpers (`load_fixture`, `render_entries_to_png`, `render_group_to_png`) live in `tests/_helpers.py`. Tags: `phase-4-complete`, `pre-phase-5-cleanup`.

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
