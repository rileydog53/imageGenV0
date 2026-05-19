# imageGen — Project Roadmap

**Status:** v1.0 — all 8 phases complete.

## Quick Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Project Setup | ✅ DONE |
| 1 | Intermediate Representation (IR) | ✅ DONE |
| 2 | Primitive Library | ✅ DONE |
| 3 | Layout Engines | ✅ DONE |
| 4 | Style Presets | ✅ DONE |
| 5 | Renderer & Compositor | ✅ DONE |
| 6 | Verification | ✅ DONE |
| 7 | LLM Frontend (SKILL.md) | ✅ DONE |
| 8 | Integration & Polish | ✅ DONE |

**Total tests passing:** 373 green ✅

---

## What's Done (Phases 0–7)

- **Phase 0:** Project initialized, deps installed, 22 smoke tests.
- **Phase 1:** Complete IR schema (Pydantic models + validators), 12 fixture JSONs.
- **Phase 2:** Primitive library — 7 modules (arrows, proteins, membranes,
  nucleic_acids, cells, chemistry, lab_equipment).
- **Phase 3:** 4 layout engines (reaction, pathway, panel, label_placement).
- **Phase 4:** 3 JSON style presets (cell_press, nature, acs) + Pydantic loader.
- **Phase 5:** `render/compositor.py` dispatches PATHWAY / REACTION_SCHEME /
  multi-panel figures; PNG + PDF export; package restructured to `imageGen/`;
  argparse CLI (`python -m imageGen`).
- **Phase 6:** verification suite — `semantic_check.py`, `legibility_check.py`,
  `convention_check.py` (fail-loud audits over the rendered SVG), plus
  golden-image regression (`tests/test_golden_images.py` + `tests/golden/`).
- **Phase 7:** `SKILL.md` — the model-facing interface (trigger rules,
  classify → IR → render → verify workflow, IR reference, refusal scripts,
  cookbook). Compositor wired so all 5 archetypes render standalone.

See `~/Desktop/TODO.txt` COMPLETED section for per-step detail + commit SHAs.

---

## What's Next

v1.0 is shipped — all eight phases are complete, all golden tests pass, and
one worked example per archetype is committed (`references/examples/`).
Future work is tracked in `BACKLOG.md`; known v1 limitations are documented
in `LIMITATIONS.md`; wrong-figure reports go in `FEEDBACK.md`.

---

## Workflow per Step

1. **Scope** — restate the step, flag ambiguities. No code yet.
2. **Test plan** — propose 2–4 concrete tests. Get approval.
3. **Implement** — code + tests in one change.
4. **Verify** — run pytest, show output.
5. **Simplify** — run `/simplify` to review for reuse/quality.
6. **Commit** — three commits: `docs:` → `feat:` → `test:`.
7. **TODO update** — update `~/Desktop/TODO.txt` (date + commit SHA).

---

## Key Files

- **`ir/schema.py`** — the IR. Don't change the schema without asking Joey.
- **`layout/reaction_layout.py`** — establishes the LayoutEntry pattern.
- **`primitives/*.py`** — visual building blocks; layout code composes them.
- **`tests/fixtures/`** — hand-crafted IR JSONs for regression testing.
- **`~/Desktop/TODO.txt`** — authoritative task list. Lives outside the repo.
- **`DECISIONS.md`** — cross-phase architectural choices (D1–D4).
- **`BACKLOG.md`** — everything deliberately deferred.

---

## Hard Rules

1. **No SVG strings.** Always `svgwrite` element objects.
2. **Every IR field is validated.** No raw dicts.
3. **Every primitive gets a golden-image test.**
4. **Plan before code.** Propose, get a green light, then build.
5. **Conventions over creativity.** Follow how Nature/Cell draws it.
6. **All files live in `~/Desktop/imageGen-v0.1/` during dev.**

(Full Hard Rules + Workflow Lessons are in `~/Desktop/TODO.txt`.)

---

## Stretch Goals (Don't Build in v1)

Force-directed label placement · automatic palette selection · BioPAX import
· 3D structure integration via PyMOL · animated figures · LaTeX export.

---

## Success Criteria (v1 Done)

- All eight phases complete
- All golden-image tests passing
- Joey can run a real prompt end-to-end, get a journal-quality figure
- Documented limitations and feedback path
- One worked example per archetype committed
