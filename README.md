# imageGen

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

- **Phase:** 8 (integration & polish) next — Phases 0–7 complete
- **Tests:** 361 passing ✅
- **Next task:** See `~/Desktop/TODO.txt` IN PROGRESS — Phase 8
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
| 5 | Renderer & compositor | ✅ Done (2026-05-14, all 6 steps: PATHWAY + REACTION_SCHEME + PANEL dispatch in `compositor.py`; PNG + PDF via `render/export.py`; package restructured to `imageGen/`; argparse CLI in `render/cli.py`) |
| 6 | Verification suite | ✅ Done (4 steps: `verify/semantic_check.py`, `verify/legibility_check.py`, `verify/convention_check.py`, golden-image regression) |
| 7 | LLM frontend (`SKILL.md`) | ✅ Done (model-facing `SKILL.md`; compositor wired for all 5 archetypes) |
| 8 | Integration & polish | ⬜ Pending |

Current test count: **361 green**. Phases 0–7 complete.

Per-step detail (what shipped, commit SHAs, locked design decisions) lives in
`~/Desktop/TODO.txt` COMPLETED section. Cross-phase architectural decisions
(IR-id tagging, watermark stub, label auto-invoke, `smiles_map`) are in
`DECISIONS.md` (D1–D4). Deferred work is tracked in `BACKLOG.md`.

Recent highlights:
- **Phase 5:** `render/compositor.py` dispatches PATHWAY / REACTION_SCHEME /
  multi-panel figures; `render/export.py` adds cairosvg-backed PNG + PDF;
  repo restructured into an installable `imageGen/` package; argparse CLI
  via `python -m imageGen`.
- **Phase 6:** four-part verification suite. Three fail-loud audits over the
  rendered SVG — `semantic_check` (every IR element present),
  `legibility_check` (text overlap / undersized fonts; returns a `needs_crop`
  signal), `convention_check` (inhibition T-bars, entity shape by type) — plus
  golden-image regression (`tests/test_golden_images.py`): 12 curated fixtures
  rendered and pixel-diffed against checked-in goldens in `tests/golden/`.
  Regenerate goldens with `IMAGEGEN_REGEN_GOLDEN=1 pytest`.
- **Phase 7:** `SKILL.md` (repo root) — the model-facing interface: trigger
  rules, the mandatory classify → IR → render → verify workflow, IR reference,
  refusal scripts, and an archetype cookbook. The compositor's `_dispatch_layout`
  now routes all pathway-compatible archetypes (WORKFLOW, CELLULAR_SCHEMATIC,
  MECHANISM_CARTOON) to `layout_pathway`, so all five archetypes render
  standalone.
- **Layout/test homes:** `LayoutEntry` in `layout/types.py`; `ENTITY_BBOX` +
  `ENTITY_TO_PRIMITIVE` in `layout/_geom.py`; shared test helpers in
  `tests/_helpers.py`. Tags: `phase-4-complete`, `pre-phase-5-cleanup`.

## Plan

The full implementation plan lives in `~/Desktop/TODO.txt` (master) and is mirrored in `TODO.md` here. The TODO file's `IN PROGRESS:` section always reflects the current step.

## Project Conventions

- **Location:** `~/Desktop/imageGen-v0.1/` — graduated to a versioned project folder (v0.1, 2026-05-18).
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
