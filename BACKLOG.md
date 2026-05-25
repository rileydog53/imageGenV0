# V2 Backlog

Single-source aggregator for V2 implementation items and stretch goals.
v1.0 is feature-complete; v1.1 added orthogonal routing and reagent labels.
**Three buckets:** **v1 Cleanup (Complete)** (code-org debt from v1), **V2 Implementation** (known functional gaps to unlock in V2), **V2 Stretch** (post-V2 goals).
Priority: high = blocks reading the codebase; medium = shows up in real
figures soon; low = polish / advanced use cases.

---

## ⚠ Rendering Bugs Discovered in Live Testing (cisplatin `cellular_schematic`, 2026-05-23)

Rendered a 7-entity, 4-compartment `cellular_schematic` figure (Cisplatin → Passive Diffusion → Activated Cisplatin → Pt–DNA Adducts → Replication Block → Apoptosis → Cell Lysis). Four concrete defects observed. Items L15–L19 below track fixes; each entry includes the exact file/function and the change needed.

| Defect | Screenshot observation | Root cause | Fix item |
|--------|----------------------|------------|----------|
| Entity bbox overflow | "Activated Cisplatin" and "N7 crosslink" label cut off at right canvas edge | `_graph_positions` places entity **centers** anywhere in [0, canvas_w]; half-bbox width overflows SVG viewport | **L15** |
| Arrow label overflow | Arrow label text near canvas edge is clipped | `place_labels` has no canvas-bounds check; candidates outside [0,W]×[0,H] are scored the same as in-bounds ones | **L18** |
| U-shaped linear chain | Cisplatin ends up top-right, Cell Lysis top-left — spring layout ignores DAG direction | `nx.spring_layout` has no concept of topological order; all-zero initial positions let it settle in any orientation | **L16** |
| Cross-compartment arrows | Arrows between different bands are straight lines that cross band label text and borders | Arrow routing does not consult compartment membership; no waypoints are injected at band boundaries | **L17** |
| Empty canvas bottom | Verifier flags `needs_crop=True`; bottom ~250 px of SVG is white | `compute_pathway_canvas` clamps to `max(sum_dynamic, 600)`; when bands sum to <600 the extra whitespace is dead | **L19** |

---

## 1. v1 Cleanup (Complete)

All v1 cleanup items resolved. Kept for reference:

| # | Item | Source | Completed |
|---|---|---|---|
| C4 | Rename module-level `DEFAULT_LAYOUT_PARAMS` symbols to engine-specific names. | — | ✓ Renamed to `REACTION_DEFAULT_PARAMS`, `PATHWAY_DEFAULT_PARAMS`, `PANEL_DEFAULT_PARAMS`, `LABEL_DEFAULT_PARAMS`. |
| C5 | `ENTITY_BBOX` table keep in sync with primitive defaults. | — | ✓ Table already in sync; added `tests/test_geom.py::test_entity_bbox_matches_primitive_defaults` to catch future drift. |

---

## 2. V2 Implementation Backlog (32 items — 5 added from live-testing 2026-05-23)

### Layout

| # | Item | Source | Priority |
|---|---|---|---|
| L1 | Force-directed arrow routing (crossing detection, curve-around heuristics). v1 drew all pathway arrows as straight bbox-to-bbox lines. | `pathway_layout.py:32`; ROADMAP §Stretch | **Medium** |
| L2 | Force-directed label placement for dense pathways. v1 was greedy with priority-ordered candidates; raises `LabelPlacementError` when boxed in. V2 could shrink font, add leader lines, or fall back gracefully. | `label_placement.py:25`; ROADMAP §Stretch | **Medium** |
| L3 | ~~Vertical sub-stacking inside a compartment band when entity count overflows canvas width.~~ **Done** — `_compute_band_heights` replaces equal-split with per-band row-aware sizing (`_BAND_BASELINE` + `_LABEL_MARGIN` constants); `compute_pathway_canvas` unified in `pathway_layout.py` and thinly delegated from compositor; 5 new tests added. | `you-re-working-as-the-giggly-cocke.md` §Out of scope | ~~Medium~~ |
| L4 | ~~Per-arrow annotation glyphs (e.g. a "P" badge on phosphorylation arrows). v1 routes `PHOSPHORYLATES` to `activation_arrow` with no decoration; V2 can add relation-specific visual marks.~~ **Done** — `_phosphorylation_arrow` wraps `activation_arrow` and overlays a circular "P" badge via `_relation_glyph`; `_PHOSPHO_BADGE_DEFAULTS` style keys respond to journal presets; `RELATION_TO_ARROW[PHOSPHORYLATES]` updated; 7 new tests added. | `pathway_layout.py:23-27`; TODO.txt §pathway | ~~Medium~~ |
| L5 | Per-entity sublabels / badges via `label_placement` (entity-anchored requests, not just relation-arrow midpoints). | `label_placement.py` plan; this-step plan §Out of Scope | **Low** |
| L6 | Per-entity primitive override via `entity.style["primitive"]` (let an IR author pick a non-default primitive for a given entity). | `you-re-working-as-the-giggly-cocke.md` §Out of scope | **Low** |
| L7 | `GENE` entity type currently maps to `generic_protein`. Lift to a nucleic-acids helix primitive once visual conventions are nailed down. | `pathway_layout.py:39-40` | **Low** |
| L8 | ~~Compartment bands render as coloured rect + label. Dedicated organelle outlines (lipid bilayer for membrane bands, double ring for nuclear envelope) belong in archetype code, not the layout engine.~~ **Done** — `_compartment_band` gains `compartment_type` kwarg; `_draw_bilayer_border` and `_draw_nuclear_border` helpers add decorations for `MEMBRANE`/`NUCLEUS` types respectively; `layout_pathway` threads compartment type into band entries; 4 new tests added. | `pathway_layout.py:41-43` | ~~Medium~~ |
| L9 | ~~`pathway_layout` does not forward a `size` kwarg to entity primitives — they all use primitive defaults.~~ **Done** — added `pathway_entity_scale` (default 1.0) to `PATHWAY_DEFAULT_PARAMS`; `effective_bbox` computed at layout time and forwarded as `size=` to every entity primitive; arrow routing and row-height calculations updated in lock-step. 5 new tests added. | `pathway_layout.py:36-38`; `phase4-style-presets.md` | ~~Medium~~ |
| L10 | Nested panel grids (`Panel.content` containing another `Figure` with `panels`). v1 raises `NotImplementedError` (depth = 1 only); V2 can lift to arbitrary nesting. | `panel_layout.py:31, 231` | **Low** |
| L11 | `panel_layout` accepts a single global `style_dict`; per-panel style overrides not supported in v1. | TODO.txt §panel DONE | **Low** |
| L12 | Panel chrome supports left-anchored title text only. Center / right alignment, multi-line titles deferred. | TODO.txt §panel DONE | **Low** |
| L13 | Allow labels to overlap arrow shafts (v1 doesn't include arrows in collision checks). A future `legibility_check` can surface visible problems; add arrow-bbox channel later if needed. | `label_placement.py:34-36` | **Low** |
| L14 | Label fallback heuristics when greedy placement exhausts candidates (v1 raises `LabelPlacementError`). V2 can shrink font, add leader lines, or fall back gracefully. | this-step plan §Open Design Choices | **Low** |
| L15 | ~~**Entity bbox overflow at canvas edges.** `_graph_positions` (in `pathway_layout.py`) places entity centres anywhere in `[origin_x, canvas_w] × [origin_y, canvas_h]`, so entities near the edge have half their bounding box outside the SVG viewport — labels and shapes are clipped. **Fix:** after `nx.spring_layout` scaling, clamp each centre: `x = clamp(x, edge_margin + w/2, canvas_w - edge_margin - w/2)` and `y = clamp(y, band_top + edge_margin + h/2, band_bottom - edge_margin - h/2)` where `(w, h) = effective_bbox[e.type]`. Add `pathway_edge_margin: 8.0` to `PATHWAY_DEFAULT_PARAMS`. Discovered in cisplatin figure (2026-05-23).~~ **Done** — `_graph_positions` gains `edge_margin` param (default 8.0 px); clamping applied to both x and y after even-spacing; `pathway_edge_margin` added to `PATHWAY_DEFAULT_PARAMS`; golden images regenerated. | `pathway_layout.py::_graph_positions` | ~~High~~ |
| L16 | ~~**DAG-aware initial positions for spring layout.** For linear-chain graphs (A→B→C→D) the spring layout produces U-shapes or crossed arrows because all nodes start at zero / random positions. **Fix:** before calling `nx.spring_layout`, check `nx.is_directed_acyclic_graph(G)`. If true, assign `x_init[node] = rank / max_rank` using `nx.topological_generations`; pass `pos=initial_pos` to `spring_layout` so the relaxation starts from a left-to-right arrangement. Falls back to unconstrained spring if cycles are detected. Discovered in cisplatin figure (2026-05-23).~~ **Done** — `_graph_positions` builds a parallel `DiGraph`; for DAGs, `nx.topological_generations` seeds x-positions before spring relaxation; cycles fall back to unconstrained spring; 1 test updated (topological order assertion), 3 goldens regenerated. 511 tests pass. | `pathway_layout.py::_graph_positions` | ~~Medium~~ |
| L17 | ~~**Cross-compartment arrow elbow routing.** Arrows between entities in different compartment bands are straight bbox-to-bbox lines; they visually cross band label text, band border lines, and unrelated entities in intermediate bands. **Fix:** in `layout_pathway`, for each relation where `location_map[source] != location_map[target]`, inject waypoints at the band boundaries: `[exit(src), (src_cx, boundary_y), (tgt_cx, boundary_y), exit(tgt)]`. Use the midpoint of the two band-boundary y-values as the routing channel. This is a subset of L1 (general crossing detection) but self-contained for the common compartment-crossing case. Discovered in cisplatin figure (2026-05-23).~~ **Done** — `_orthogonal_waypoints` already routes all arrows (same-band and cross-band) through the inter-band corridor; call-site in `layout_pathway` applies it to every relation unconditionally (verified 2026-05-25). | `pathway_layout.py::layout_pathway` (arrow-emit loop) | ~~Medium~~ |
| L18 | ~~**Label placement canvas-bounds filter.** `place_labels` in `label_placement.py` scores and places labels without knowing the canvas size. Candidates whose text bbox would fall outside `[0, canvas_w] × [0, canvas_h]` are placed anyway, causing visible clipping at the SVG edge. **Fix:** add `canvas: tuple[float, float] | None = None` kwarg to `place_labels`; before the overlap check, eliminate any candidate whose `(x - text_w/2, y - text_h/2, x + text_w/2, y + text_h/2)` intersects `x < 0` or `x > canvas_w` or similar. Compositor must forward `canvas` when calling `place_labels`. Discovered in cisplatin figure (2026-05-23).~~ **Done** — `canvas` kwarg added to `_first_fit`, `_place_with_fallback`, and `place_labels`; out-of-bounds candidates skipped before overlap check; compositor computes canvas early and forwards it to all `place_labels` call-sites (including `_place_labels_per_panel`). | `label_placement.py::place_labels`; `compositor.py::render_figure` | ~~High~~ |
| L19 | ~~**Dead whitespace at canvas bottom after dynamic band heights (L3).** `compute_pathway_canvas` clamps the result to `max(sum_dynamic_heights, 600)`. When 4 compact bands sum to ~350 px, the SVG has ~250 px of empty white at the bottom, which the legibility verifier correctly flags as `needs_crop=True`. **Fix:** change the lower bound from the hardcoded `600` to `n_bands * _BAND_BASELINE` (e.g. 4 bands × 100 px = 400 px). This keeps each band at minimum baseline height without adding dead canvas space beyond the content. In `compute_pathway_canvas` (`pathway_layout.py`), replace `max(float(min_h), sum(heights))` with `max(n_bands * _BAND_BASELINE, sum(heights))`. Discovered in cisplatin figure (2026-05-23).~~ **Done** — one-liner change in `compute_pathway_canvas`; test floor expectations updated to 100 px for single-band figures; golden images regenerated. | `pathway_layout.py::compute_pathway_canvas` | ~~Low~~ |

### Reaction layout

| # | Item | Source | Priority |
|---|---|---|---|
| R1 | ~~Vertical stacking when reactant/product count would overflow panel width. v1 lays everything out horizontally; V2 can add column wrapping.~~ **Done** — `_should_stack` computes total flat width; `layout_reaction` forwards `stack=True` + `stacked_row_gap` when width exceeds `reaction_max_width`; `render_reaction` gains `stack` parameter placing reactants on row 1 and arrow+products on row 2; 6 new tests added. | `reaction_layout.py:25-28` | ~~Medium~~ |
| R2 | ~~`ReactionConditions.reversible` is silently ignored — chemistry's arrow primitive only draws single-direction.~~ **Done** — `_reversible_arrow` draws forward (↑) + backward (↓) half-arrows; `render_reaction` gains `reversible` parameter; `_is_reversible(figure)` detects the flag in any relation's conditions; `layout_reaction` forwards `reversible=True` when set; `chem_reaction_reversible_gap` added to `DEFAULT_STYLE`; 5+5 new tests added. | `reaction_layout.py:29-31` | ~~Medium~~ |
| R3 | Multi-step reactions (an entity that is both source and target of different relations — an intermediate) raise `NotImplementedError`. V2: route to `pathway_layout.py` (official answer). | `reaction_layout.py:32-34` | **Low** |
| R4 | ~~Per-molecule annotations / compound numbers. V2 `reaction_layout` can decompose into per-molecule `LayoutEntry` items, paired with `label_placement`.~~ **Done** — `_molecule_centers` replicates `render_reaction` cursor geometry to compute each molecule's (cx, cy); `reaction_label_requests(fig, entries)` emits one `LabelRequest` per entity with `priority=("below", ...)` and `ir_id=entity.id`; compositor `_label_requests_fn` now returns it for REACTION_SCHEME; 7 new tests added. | `reaction_layout.py:35-37, 165` | ~~Medium~~ |
| R5 | Per-arrow conditions in multi-step reactions (different conditions per arrow). v1 uses the first relation's conditions; V2 can honor each arrow's conditions independently. | `reaction_layout.py:109` | **Low** |

### Primitives

| # | Item | Source | Priority |
|---|---|---|---|
| P1 | True 3D ball-and-stick chemistry rendering. v1's `style="ball_stick"` is 2D (larger atom labels, wider bonds, visual 3D lean); V2 could lift to full 3D. | `chemistry.py:8`; `phase2-step6-chemistry.md` | **Low** |
| P2 | Bond-line packing fixes for crowded chemistry diagrams. V2 Stretch (ties to verification suite). | `chemistry.py:12` | **Low** |
| P3 | ~~`_centered_label` helper currently lives in `proteins.py` and is imported across modules. Promote to shared `primitives/_text.py` or fold into style loader.~~ **Done** — created `primitives/_text.py::centered_label`; `proteins.py` and `label_placement.py` now import from there. | implicit in `label_placement._label_primitive`'s reuse | ~~Low~~ |

### Styles (V2 Style System)

| # | Item | Source | Priority |
|---|---|---|---|
| ST1 | Auto-derive primitive fills from palette indices. A "recipe" layer that maps `palette[0] → protein_fill`, `palette[1] → kinase_fill`, etc. V2 can reduce preset duplication with opinionated palette-to-primitive mappings. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST2 | ~~Lift aesthetic layout-params (`pathway_band_fill`, `panel_border_stroke`, `panel_title_size`, etc.) into presets. Currently caller-set; V2 presets could carry a `layout_overrides` block.~~ **Done** — `StylePreset` gains `layout_overrides` field; `KNOWN_LAYOUT_PARAMS` (13 aesthetic keys) guards against typos; `load_layout_params(name)` convenience function added; all 3 shipped presets updated with journal-appropriate band/panel values; 8 new tests added. | `phase4-style-presets.md` §Out of Scope | ~~Medium~~ |
| ST3 | Style preset *inheritance*. ACS could declare `inherits: "cell_press"` and override only chemistry. v1 has no inheritance — V2 can add it. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST4 | Per-figure style switching mid-render. v1 assumes one preset per `render_figure` call; V2 can allow runtime preset swaps. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST5 | ~~Style validation against the *full* primitive key set. The loader could collect every primitive's `DEFAULT_STYLE` keys at import time and warn if a preset references unknown keys (typo guard).~~ **Done** — `KNOWN_STYLE_KEYS` (182 keys) assembled at import time; `load_preset_full` emits `UserWarning` on unknown override keys; 5 new tests added. | `phase4-style-presets.md` §Out of Scope | ~~Medium~~ |

---

## 3. V2 Stretch Goals (Post-Implementation)

Long-horizon items from `ROADMAP.md` §Stretch Goals and the master plan. These extend beyond V2's core functional improvements:

| # | Item | Source |
|---|---|---|
| S1 | Force-directed label placement for dense pathways | ROADMAP, TODO.txt §plan |
| S2 | Automatic palette selection based on entity types | ROADMAP, TODO.txt §plan |
| S3 | "Compile from BioPAX" — accept standardized pathway formats as input | ROADMAP, TODO.txt §plan |
| S4 | 3D protein structure integration via PyMOL handoff | ROADMAP, TODO.txt §plan |
| S5 | Animated / multi-frame figures for presentations | TODO.txt §plan |
| S6 | LaTeX export for direct manuscript inclusion | TODO.txt §plan |
| S7 | Per-arrow conditional rendering in pathways (different conditions per relation, currently only honored in reaction layout) | derived from R5 + L4 |

---

## How to use this file

**V2 Implementation:** Scan Section 2 for the next item to tackle. Work top-to-bottom by priority (High → Medium → Low), grouping related items by subsection (Layout, Reaction, Primitives, Styles).

**Stretch Goals:** Section 3 items are long-horizon. Revisit after V2 Implementation is complete.

**When discovering new work:** Add a row in the appropriate section in the same shape — don't bury decisions in module docstrings alone. Update item descriptions as implementation reveals constraints.

---

## Session state for the next chat (as of 2026-05-23)

**Waves completed:** 1 (P3, ST5), 2 (L9, ST2), 3 (L3, L8, L4), 4 (R1, R2, R4), 5 (L15, L18, L19), 6 (L17 confirmed done, L16 next).

**Wave 6 complete.** All medium-priority rendering bugs resolved (L15, L16, L17, L18, L19).

**Next:** **L1** (full force-directed arrow routing) or **L2** (force-directed label placement) — both Medium, open-ended algorithm work.

**Remaining Medium-priority items after bugs:** L1 (full force-directed routing), L2 (force-directed label placement), L13 (arrow collision in label placement), R3 (multi-step routing), R5 (per-arrow conditions).

**Test suite state:** 511 tests, 0 failures. Run `~/Desktop/.venv/bin/python -m pytest -q` to verify.

**Key files for the next wave:**
- `imageGen/layout/pathway_layout.py` — `_graph_positions` (L15, L16), arrow-emit loop in `layout_pathway` (L17), `compute_pathway_canvas` (L19)
- `imageGen/layout/label_placement.py` — `place_labels` signature + candidate filter (L18)
- `imageGen/render/compositor.py` — forward `canvas` kwarg to `place_labels` calls (L18)
