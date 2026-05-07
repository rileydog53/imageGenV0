# imageGenV0 — Project Roadmap

**Status:** Phase 3 (Layout Engines) — Step 2 of 4 starting now

## Quick Status

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| 0 | Project Setup | ✅ DONE | 22 |
| 1 | Intermediate Representation (IR) | ✅ DONE | 25 |
| 2 | Primitive Library | ✅ DONE | 102 |
| 3 | Layout Engines | 🔄 IN PROGRESS (Step 2/4) | 16 |
| 4 | Style Presets | ⏳ PENDING | — |
| 5 | Renderer & Compositor | ⏳ PENDING | — |
| 6 | Verification | ⏳ PENDING | — |
| 7 | LLM Frontend (SKILL.md) | ⏳ PENDING | — |
| 8 | Integration & Polish | ⏳ PENDING | — |

**Total tests passing:** 172 green ✅

---

## What's Done (Phases 0–3.1)

**Phase 0:** Project initialized, all dependencies installed, 22 smoke tests pass.

**Phase 1:** Complete IR schema (Pydantic models: Entity, Relation, Compartment, Figure, etc.). All validators in place. 12 fixture JSONs for testing.

**Phase 2:** Primitive library complete with 7 modules:
- `arrows.py` — activation, inhibition, binding, translocation, reaction arrows
- `proteins.py` — generic, kinase, receptor, GPCR, transcription factor
- `membranes.py` — lipid bilayer, cell membrane outline, nuclear envelope
- `nucleic_acids.py` — DNA, RNA, chromatin
- `cells.py` — cell outlines (generic, neuron, epithelial, immune) + organelles
- `chemistry.py` — RDKit molecule/reaction/functional group rendering
- `lab_equipment.py` — well plates, tubes, pipettes, gels, microscopes, animals

**Phase 3 Step 1:** `layout/reaction_layout.py` — simple left-to-right layout for reaction schemes. 16 tests, 1 fixture PNG.

---

## What's Next (Phase 3.2–3.4)

### Phase 3, Step 2: `layout/pathway_layout.py` — THE HARD ONE
**Compartment-aware biological pathway layout.** Groups entities by compartment, renders compartments as horizontal bands (extracellular → cytoplasm → nucleus), uses NetworkX graph layout to position entities, routes arrows to avoid crossings.

- **Open design choices:**
  - Compartment ordering: hardcode biological convention or read from Figure.compartments?
  - Primitive selection: dispatch dict in layout module or read from entity.style?
  - Arrow routing: simple curve-to-avoid-crossings or force-directed?
- **Entry point for next chat:** Read `layout/reaction_layout.py` (established LayoutEntry pattern), `ir/schema.py` (Compartment class), and `tests/fixtures/` for pathway examples.
- **Expected:** ~200 LOC, ~20 tests, 2–3 fixture PNGs

### Phase 3, Step 3: `layout/panel_layout.py`
Multi-panel figures. Lay out panels in a grid with consistent gutters. Recursively call the appropriate layout engine for each panel's content.

### Phase 3, Step 4: `layout/label_placement.py`
Automated label placement. Try positions in priority order (center, above, below, right, left). Pick first that doesn't overlap. Greedy v1; force-directed later.

---

## Workflow per Step (How the Team Codes)

1. **Scope** — restate the step, flag ambiguities. No code yet.
2. **Test plan** — propose 2–4 concrete tests. Get approval.
3. **Implement** — code + tests in one change.
4. **Verify** — run pytest, show output.
5. **Simplify** — run `/simplify` skill to review code for reuse/quality.
6. **Commit** — atomic, descriptive commit (pattern: `feat(module):`, `refactor:`, `test:`).
7. **TODO update** — update `~/Desktop/TODO.txt` with completion date + commit SHA.

---

## Key Files to Know

- **`ir/schema.py`** — the IR (Figure, Entity, Relation, Compartment). Don't change the schema without asking Joey.
- **`layout/reaction_layout.py`** — establishes the LayoutEntry pattern subsequent layout engines follow.
- **`primitives/*.py`** — the visual building blocks. Immutable; layout code composes them.
- **`tests/fixtures/`** — hand-crafted IR JSONs for regression testing.
- **`~/Desktop/TODO.txt`** — the authoritative task list. Lives outside the repo.

---

## Hard Rules (Pin These)

1. **No SVG strings.** Always use `svgwrite` element objects.
2. **Every IR field is validated.** No raw dicts.
3. **Every primitive gets a golden-image test.** No exceptions.
4. **Plan before code.** Propose the approach, get a green light, then build.
5. **Conventions over creativity.** Follow how Nature/Cell draws it.
6. **All files live in `~/Desktop/imageGenV0/` during dev.** Nowhere else.

---

## For New Contributors

- Read `CLAUDE.md` first — it explains the team's working style.
- Read this roadmap to see where we are.
- Read `~/Desktop/TODO.txt` `IN PROGRESS` section for the next step's requirements.
- Read the pattern file for the phase you're working on (e.g., `primitives/proteins.py` for Phase 2 style).
- Ask before deviating from the plan.

---

## Stretch Goals (Don't Build in v1)

- Force-directed label placement
- Automatic palette selection
- BioPAX format import
- 3D protein structure integration
- Animated/multi-frame figures
- LaTeX export

---

## Success Criteria (v1 Done)

- All eight phases complete
- All golden-image tests passing
- Joey can run a real prompt end-to-end, get a journal-quality figure
- Documented limitations and feedback path
- One worked example per archetype committed
