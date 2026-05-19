# Phase 8 — Integration & Polish (plan)

Final v1 phase. No new rendering code, no IR schema changes. Two steps,
each following the three-commit cadence (`docs:` → `feat:` → `test:`).

## Step 1 — End-to-end test + worked examples

- `tests/test_end_to_end.py` — exercises the full pipeline as an automated
  acceptance test. For each of the 5 archetypes: load a fixture IR →
  `render_figure(...)` → run `semantic_check`, `legibility_check`,
  `convention_check` on the rendered sibling SVG → assert a non-empty PNG.
- The three label-overflow fixtures (`graphical_abstract_mrna_vaccine`,
  `mechanism_cartoon`, `western_blot_schematic`) render with `labels=False`
  in the clean-pipeline test; a separate test asserts they raise
  `LabelPlacementError` with labels on — the limitation is tested as
  documented behavior, not hidden.
- Worked examples: one rendered PNG per archetype committed to
  `references/examples/` (satisfies the "one worked example per archetype"
  DoD item).

## Step 2 — Human documentation

- `README.md` rewritten for human developers: what it is, install, CLI
  usage, architecture, running tests.
- Agent/builder onboarding split into `CONTRIBUTING.md`.
- `LIMITATIONS.md` — greedy label placement overflow (`LabelPlacementError`,
  BACKLOG L2/L14), no 3D structures, ~20-entity practical ceiling, straight
  pathway arrows only.
- `FEEDBACK.md` — structured log template for wrong-figure notes feeding v2.

## Close-out

- All docs updated in lockstep (README status, ROADMAP, TODO.txt COMPLETED).
- Push to GitHub; tag `v1.0`.
