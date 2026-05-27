# PLAN — V2.1: Circular / Non-Linear Layout + Nucleic-Acid Primitives

**Status:** ✅ Complete — landed 2026-05-26 / 2026-05-27. All LT items below
(LT1–LT10 + the `complex` entity type) are done and ticked; suite green at
**658 tests**. The issues were found in a live natural-language testing run
(2026-05-26) across 6 figures + 1 out-of-scope request, on top of Waves 1–7
(L1–L24, R1–R6, V1, P1–P3, ST1–ST5).

> **Current milestone: v2.2** (cleanup + live testing). The V2.1 layout/primitive
> program documented here is finished; v2.2 covers the version bump to `2.2.0`,
> the SKILL.md reconciliation, stale-path fixes, and a fresh live-render sweep.
> This file is retained as the V2.1 implementation record.

> How to use this file: work the issues top-to-bottom within each priority tier.
> Each item carries **Symptom → Root cause → Files → Fix → Acceptance**. The three
> reproduction fixtures in `tests/fixtures/` (added alongside this plan) are the
> canonical repro + future regression cases. Run `~/Desktop/.venv/bin/python -m
> pytest -q` after every change. Update this file's checkboxes as you land each item.

---

## How the issues were found

A 6-figure natural-language sweep, then a deliberate out-of-scope probe:

| Fig | Prompt (natural language) | Archetype | Result |
|-----|---------------------------|-----------|--------|
| 1 | EGFR–MAPK signalling with feedback | pathway (4 compartments, cyclic) | rendered; **legibility FAIL** (P-badge vs label) |
| 2 | scRNA-seq workflow | 4-panel workflow | rendered; **legibility FAIL** (panel label crowding) |
| 3 | Glycolysis glucose→pyruvate | reaction_scheme | clean (best result) |
| 4 | Krebs / citric-acid cycle, 8 intermediates | pathway (cyclic) | rendered but **cycle reads as a line** |
| 5 | Coagulation cascade (intrinsic+extrinsic→thrombin) | pathway (convergent) | rendered but **topology lost** |
| 6 | CRISPR-Cas9 find & cut | mechanism_cartoon | rendered but **sequence scrambled**, DSB drawn as intact DNA, sgRNA drawn as DNA |
| 7 | "photorealistic golden retriever" | — | **correctly declined** (out of scope) ✅ |

Reproduction fixtures: `tests/fixtures/krebs_cycle.json`,
`tests/fixtures/coagulation_cascade.json`, `tests/fixtures/crispr_cas9.json`.

---

## Priority tiers

- **P0 (headline features the user explicitly asked for):** LT1, LT2, LT7, LT8
- **P1 (legibility defects that fail the verifier):** LT3, LT4, LT5
- **P2 (authoring correctness / robustness):** LT6, LT9

---

## P0 — Layout engine: circular & non-linear diagramming

### LT1 — Circular / ring layout for cyclic pathways  ☑
- **Symptom:** The Krebs cycle (fig 4) renders as a single horizontal band. The
  closing edge `Oxaloacetate → Citrate` and the rank back-edges arch over the top
  as long lane-routed arrows. It does not read as a cycle.
- **Root cause:** `pathway_layout._graph_positions` only ever places entities in
  horizontal compartment bands (band-snap y, evenly-spaced x). L23's
  `_feedback_arc_dag` strips the back-edge for *ranking* so the chain doesn't
  reverse, but there is no layout mode that arranges nodes on a closed ring.
- **Files:** `imageGen/layout/pathway_layout.py` (`_graph_positions`,
  `layout_pathway`, `compute_pathway_canvas`); new layout-param keys in
  `PATHWAY_DEFAULT_PARAMS`.
- **Fix:** Add a **ring layout mode**. Detect a dominant single cycle (the graph is
  one strongly-connected component, or `_feedback_arc_dag` removed exactly the edges
  that close one cycle) → place the cycle nodes on a circle (angle = rank/N · 2π),
  route arrows as arc segments (or short chords) along the ring, and put edge labels
  on the outside of the ring. Gate it behind an explicit signal first
  (`figure.layout_hint == "circular"` in the IR, or a `--layout circular` CLI flag)
  before attempting auto-detection, so existing linear pathways are untouched.
  Canvas becomes square-ish (`max(ring_diameter + margins)`).
- **Acceptance:** `krebs_cycle.json` renders 8 nodes on a ring with the 8 reactions
  as arrows between adjacent nodes and no long over-arching lane arrows; linear
  fixtures (mapk_cascade) byte-identical unless they opt in.

### LT2 — Non-linear DAG layout: ranked convergence / divergence  ☑
- **Symptom:** (a) Coagulation (fig 5): intrinsic (XII→XI→IX) and extrinsic
  (TF→VII) arms both feeding Factor X, plus cofactor V feeding prothrombin, collapse
  to a flat row; convergence is invisible and arrows arc the full width. (b) CRISPR
  (fig 6): a branchy mechanism graph lands DSB center-bottom and R-loop far right
  with criss-crossing arrows — reading order is lost.
- **Root cause:** In a single implicit band, x comes from spring-layout ordering and
  y from L20's `topo_y` sibling spread. That is not a real layered/Sugiyama layout:
  multi-input nodes (RNP ← Cas9 + sgRNA; Factor X ← IX + VII) aren't ranked by
  longest-path depth, and there's no crossing-reduction pass, so columns interleave.
- **Files:** `imageGen/layout/pathway_layout.py` (`_graph_positions`,
  `_max_topo_siblings`); possibly a new `imageGen/layout/_layered.py` helper.
- **Fix:** Replace the spring-x / topo-y heuristic for compartment-free DAGs with a
  proper **layered (Sugiyama-style) layout**: (1) rank each node by longest-path
  depth on `_feedback_arc_dag`; (2) assign x = rank-column; (3) order nodes within a
  rank to minimise edge crossings (barycenter / median heuristic, a couple of
  sweeps); (4) y = position within rank. Keep band-snap when real compartments exist.
  Convergence then reads as multiple columns funnelling into one; divergence as one
  column fanning out.
- **Acceptance:** `coagulation_cascade.json` shows the two input arms as distinct
  left columns converging on Factor X / prothrombin / thrombin in a clean left-to-
  right rank order; `crispr_cas9.json` reads Cas9+sgRNA → RNP → PAM/R-loop → DSB in
  order with no arrow crossings.

### LT7 — Broken DNA strand primitive (double-strand break glyph)  ☑
- **Symptom:** In the CRISPR fig the "Double-strand break" entity renders as an
  ordinary intact double helix — semantically wrong; a DSB should show a gap.
- **Root cause:** `nucleic_acids.dna_segment` has no break/gap mode; `gene_helix`
  always draws a continuous double helix.
- **Files:** `imageGen/primitives/nucleic_acids.py` (extend `dna_segment` +
  `gene_helix`); `imageGen/layout/_geom.py` if a new primitive/entity is registered;
  tests in `tests/test_primitives_nucleic_acids.py`.
- **Fix:** Add `broken: bool = False` (and optional `break_position: float = 0.5`)
  to `dna_segment`. When set, omit a small axis interval around `break_position` on
  **both** strands and draw clean (or jagged) blunt ends, optionally with a small
  offset between the two cut ends so the break is unmistakable. Surface it via
  `gene_helix(..., broken=True)` and/or a style flag, so an IR author can mark an
  entity as a DSB (e.g. `entity.style["dna_break"] = true`).
- **Acceptance:** A unit test renders a broken segment and asserts there are two
  strand polylines with a coordinate gap at the break; the CRISPR DSB node visibly
  shows the break.

### LT8 — RNA entity type + routing (wire the existing `rna_segment`)  ☑
- **Symptom:** sgRNA in the CRISPR fig rendered as a blue **DNA double helix**, not
  an RNA strand. RNA species have no way to render correctly.
- **Root cause:** `nucleic_acids.rna_segment` (orange single strand) exists but is
  **not wired to any entity type**. `EntityType.GENE` always maps to `gene_helix` →
  `dna_segment`. There is no `EntityType.RNA`.
- **Files:** `imageGen/ir/schema.py` (add `EntityType.RNA = "rna"`);
  `imageGen/layout/_geom.py` (`ENTITY_BBOX`, `ENTITY_TO_PRIMITIVE`,
  `PRIMITIVE_REGISTRY`); new `rna_helix(label, position, size, color, style_dict)`
  wrapper in `nucleic_acids.py` mirroring `gene_helix` but calling `rna_segment`;
  `convention_check._PRIMITIVE_SHAPE`; SKILL.md schema; tests.
- **Fix:** Add the `RNA` entity type, an `rna_helix` entity-primitive wrapper (orange
  single strand + label below), and register it. mRNA / sgRNA / miRNA species then
  render distinctly from DNA.
- **Acceptance:** An IR entity with `"type": "rna"` renders an orange single-strand
  helix; CRISPR sgRNA (re-encoded as `rna`) is visually distinct from Target DNA.

---

## P1 — Legibility defects (these FAIL `--verify`)

### LT3 — Phosphorylation "P" badge collides with the arrow label  ☑
- **Symptom:** MAPK fig: legibility FAIL — the red "P" badge and the relation label
  ("translocate") both sit at the arrow midpoint and overlap.
- **Root cause:** `pathway_layout._phosphorylation_arrow` draws the badge at
  `_midpoint_of_path(...)`, and `pathway_label_requests` anchors the label at the
  *same* midpoint. Neither knows about the other; the badge isn't in the label
  engine's `occupied` set.
- **Files:** `imageGen/layout/pathway_layout.py` (`_phosphorylation_arrow`,
  `pathway_label_requests`); possibly feed the badge bbox into
  `label_placement.place_labels` as an occupied region.
- **Fix:** Either (a) offset the badge slightly off-midpoint along the shaft and feed
  its bbox into the label engine's `occupied` list so labels avoid it, or (b) when a
  relation has both a badge and a label, bias the label's priority to the
  perpendicular side opposite the badge. (a) is more general.
- **Acceptance:** `mapk` repro renders with `--verify` reporting `legibility=OK`.

### LT4 — Panel-local label placement ignores panel cell width  ☑
- **Symptom:** scRNA-seq fig: entity labels overlap badly inside the narrow panel
  columns ('Tissue sample' / 'Enzymatic digestion'); legibility FAIL.
- **Root cause:** `compositor._place_labels_per_panel` passes the **full figure
  canvas** (800×600) as the `canvas=` bound to `place_labels`, not the panel's
  allocated cell. Entities are also spaced by the sub-engine without accounting for
  label width, so wide labels collide before placement even runs.
- **Files:** `imageGen/render/compositor.py` (`_place_labels_per_panel` — compute and
  pass the per-panel cell bbox); `imageGen/layout/panel_layout.py` (entity x-spacing
  could grow with label extent); `imageGen/layout/pathway_layout.py`
  (`compute_pathway_canvas` label-extent width is still a "future refinement").
- **Fix:** Pass each panel's cell `(w, h)` (and origin) as the canvas bound for that
  panel's `place_labels` call so out-of-cell candidates are filtered. Add label-width
  to the inter-entity spacing in `compute_pathway_canvas` / sub-engine layout so wide
  labels get horizontal room.
- **Acceptance:** `scrnaseq` repro renders with `legibility=OK`.

### LT5 — `needs_crop=True` on nearly every figure (autocrop not on the deliverable)  ☑
- **Symptom:** Every figure reports `needs_crop=True`; figures ship with dead margin.
- **Root cause:** L22 added `render_figure(autocrop=...)` but it defaults **False**,
  and neither the CLI nor the skill passes it. The existing `--crop` flag writes a
  *sibling* `*_cropped` file rather than trimming the main deliverable.
- **Files:** `imageGen/render/cli.py` (add `--autocrop` that sets
  `render_figure(autocrop=True)`, or make crop-in-place the default for the primary
  output); `~/.claude/skills/imageGen/SKILL.md` (pass the flag in the documented CLI
  invocation).
- **Fix:** Add `--autocrop` to the CLI wired to `render_figure(autocrop=True)`, and
  update SKILL.md's run command to use it so figures ship tight by default. Keep the
  golden-test default at `autocrop=False` (do **not** flip the library default, or
  goldens move).
- **Acceptance:** Running the documented skill command yields a figure whose
  `--verify` reports `needs_crop=False` (or no dead margin).

---

## P2 — Authoring correctness & robustness

### LT6 — SKILL.md schema enum list is wrong  ☑
- **Symptom:** The skill prompt lists entity types `process`, `step`, `complex` and
  relation types `produces`, `consumes` — **all rejected** by the validator. Hit on
  3 of 6 figures, each needing a fix-and-rerun.
- **Root cause:** SKILL.md drifted from `imageGen/ir/schema.py`. Real enums:
  - EntityType: `protein, ligand, receptor, kinase, gene, metabolite, cell,
    organelle, equipment, sample, generic` (+ `rna` once LT8 lands).
  - RelationType: `activates, inhibits, binds, translocates, phosphorylates,
    transcribes, generic`.
- **Files:** `~/.claude/skills/imageGen/SKILL.md`; optionally `imageGen/ir/schema.py`
  if we decide to **add** types.
- **Fix:** First, correct the SKILL.md lists to match the schema exactly. Then decide
  (separately) whether to *add* genuinely-useful types: `produces`/`consumes`
  relations carry real metabolic/reaction semantics and would reduce the "everything
  is generic" smell; `complex` as an entity type is commonly wanted. If added, update
  schema + dispatch + convention_check + tests, not just the doc.
- **Acceptance:** Every reproduction fixture validates **without** type remapping.
- **Resolution (2026-05-26):** SKILL.md enum lists synced to the schema (entity,
  relation, **and** compartment types; corrected the `contains`→`location`
  compartment shape and the `conditions` fields). Add-types decision: **added
  `EntityType.COMPLEX`** (renders as two overlapping rounded rects via
  `proteins.protein_complex`; wired through `_geom`, `convention_check`, SKILL.md,
  tests). Declined `produces`/`consumes` (overlap existing `reaction_scheme`
  reactant→product modeling) — left as a future option.

### LT9 — Formalize the out-of-scope scope-guard in SKILL.md  ☑
- **Symptom:** The photorealistic-dog decline (fig 7) worked, but only because the
  agent recognised scope ad-hoc. Nothing in the skill formally instructs refusal.
- **Root cause:** SKILL.md describes what the skill *does* but has no explicit "refuse
  these" guard.
- **Files:** `~/.claude/skills/imageGen/SKILL.md`.
- **Fix:** Add a short **"Out of scope — decline these"** section: photorealistic /
  raster / illustrative images, plots of real quantitative data, logos/art, anything
  not expressible as a schematic IR. Instruct a one-line explanation + redirect
  (diffusion model for images, plotting library for data) rather than emitting a
  degenerate "labelled box" figure.
- **Acceptance:** The documented behaviour matches what happened in fig 7.

---

## Suggested implementation order

1. **LT2** (layered DAG) — highest leverage; fixes convergence + the single-band
   ordering scramble at once, and is the foundation LT1 builds on.
2. **LT1** (ring layout) — depends on clean ranking from LT2.
3. **LT8 + LT7** (RNA entity + broken-DNA) — self-contained primitive work, can run
   in parallel with the layout track.
4. **LT3, LT4, LT5** (legibility trio) — independent, each closes a verifier FAIL.
5. **LT6, LT9** (SKILL.md correctness + scope-guard) — doc-only, do anytime; LT6's
   "add new types" decision may wait on LT8.

## Definition of done

- All three reproduction fixtures render with `--verify` reporting `semantic=OK
  legibility=OK convention=OK` and read correctly (cycle as a ring, convergence as
  ranks, mechanism in sequence, RNA orange, DSB visibly broken).
- New tests cover each landed item; full suite green
  (`~/Desktop/.venv/bin/python -m pytest -q`).
- SKILL.md enum lists match the schema; scope-guard documented.
- Update `BACKLOG.md` "Session state" and tick the checkboxes above as items land.

## Key files (entry points for a cold start)

- `imageGen/layout/pathway_layout.py` — `_graph_positions` (LT1, LT2),
  `_phosphorylation_arrow` + `pathway_label_requests` (LT3),
  `compute_pathway_canvas` (LT1, LT4).
- `imageGen/render/compositor.py` — `_place_labels_per_panel` (LT4), `_autocrop_svg`
  + `render_figure(autocrop=)` (LT5).
- `imageGen/render/cli.py` — `--autocrop` wiring (LT5).
- `imageGen/primitives/nucleic_acids.py` — `dna_segment`/`gene_helix` (LT7),
  `rna_segment` + new `rna_helix` (LT8).
- `imageGen/ir/schema.py` — `EntityType` (LT8), enum source of truth (LT6).
- `imageGen/layout/_geom.py` — `ENTITY_BBOX` / `ENTITY_TO_PRIMITIVE` /
  `PRIMITIVE_REGISTRY` (LT7, LT8).
- `~/.claude/skills/imageGen/SKILL.md` — enum lists, run command, scope-guard
  (LT5, LT6, LT9).
