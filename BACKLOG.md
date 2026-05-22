# Backlog

Single-source aggregator for every "out of scope" / "deferred" / "v2"
item as of v1.0. Three buckets: **Cleanup** (code-org debt, no behavior
change), **Deferred to v2** (known functional gaps), **Stretch** (post-v1).
Priority: high = blocks reading the codebase; medium = shows up in real
figures soon; low = polish / advanced use cases.

---

## 1. Cleanup

| # | Item | Source | Priority |
|---|---|---|---|
| C4 | Rename module-level `DEFAULT_LAYOUT_PARAMS` symbols (clash across `reaction_layout.py`, `pathway_layout.py`, `panel_layout.py`, `label_placement.py`) to engine-specific names like `PATHWAY_DEFAULT_PARAMS` if star-imports ever become necessary. | `reaction_layout.py` etc. | **Low** |
| C5 | `ENTITY_BBOX` table (in `layout/_geom.py`) tracks each protein primitive's *default* size — keep in sync if a primitive's default size changes. | `layout/_geom.py` | **Medium** |

---

## 2. Deferred to v2 (functional gaps)

### Layout

| # | Item | Source | Priority |
|---|---|---|---|
| L1 | Force-directed arrow routing (crossing detection, curve-around heuristics). v1 draws all pathway arrows as straight bbox-to-bbox lines. | `pathway_layout.py:32`; ROADMAP §Stretch | **Medium** |
| L2 | Force-directed label placement for dense pathways. v1 is greedy with priority-ordered candidates; raises `LabelPlacementError` when boxed in. | `label_placement.py:25`; ROADMAP §Stretch | **Medium** |
| L3 | Vertical sub-stacking inside a compartment band when entity count overflows canvas width. | `you-re-working-as-the-giggly-cocke.md` §Out of scope | **Medium** |
| L4 | Per-arrow annotation glyphs (e.g. a "P" badge on phosphorylation arrows). Currently `PHOSPHORYLATES` routes to `activation_arrow` with no decoration. | `pathway_layout.py:23-27`; TODO.txt §pathway | **Medium** |
| L5 | Per-entity sublabels / badges via `label_placement` (entity-anchored requests, not just relation-arrow midpoints). | `label_placement.py` plan; this-step plan §Out of Scope | **Low** |
| L6 | Per-entity primitive override via `entity.style["primitive"]` (let an IR author pick a non-default primitive for a given entity). | `you-re-working-as-the-giggly-cocke.md` §Out of scope | **Low** |
| L7 | `GENE` entity type currently maps to `generic_protein`. Lift to a nucleic-acids helix primitive once visual conventions are nailed down. | `pathway_layout.py:39-40` | **Low** |
| L8 | Compartment bands render as coloured rect + label. Dedicated organelle outlines (lipid bilayer for membrane bands, double ring for nuclear envelope) belong in archetype code, not the layout engine. | `pathway_layout.py:41-43` | **Medium** |
| L9 | `pathway_layout` does not forward a `size` kwarg to entity primitives — they all use primitive defaults. Originally tagged "lift during Phase 4"; reclassified as layout cleanup (not style work) and deferred again. Lift before Phase 5 ships if entity sizing matters; otherwise after. | `pathway_layout.py:36-38`; `phase4-style-presets.md` reclassification | **Medium** |
| L10 | Nested panel grids (`Panel.content` containing another `Figure` with `panels`). v1 raises `NotImplementedError`; depth = 1. | `panel_layout.py:31, 231` | **Low** |
| L11 | `panel_layout` accepts a single global `style_dict`; per-panel style overrides not supported in v1. | TODO.txt §panel DONE | **Low** |
| L12 | Panel chrome supports left-anchored title text only. Center / right alignment, multi-line titles deferred. | TODO.txt §panel DONE | **Low** |
| L13 | Allow labels to overlap arrow shafts in v1 (the engine doesn't include arrows in collision checks). Phase 6's `legibility_check` will surface visible problems. Could add an arrow-bbox channel later if needed. | `label_placement.py:34-36` | **Low** |
| L14 | Label fallback: when greedy placement exhausts every candidate the engine raises `LabelPlacementError`. v2 could shrink font size, add a leader line, or fall back to "right" with a warning. | this-step plan §Open Design Choices | **Low** |

### Reaction layout

| # | Item | Source | Priority |
|---|---|---|---|
| R1 | Vertical stacking when reactant/product count would overflow panel width. v1 lays everything out horizontally. | `reaction_layout.py:25-28` | **Medium** |
| R2 | `ReactionConditions.reversible` is silently ignored — chemistry's arrow primitive only draws single-direction. Honor once chemistry exposes a reversible-arrow option. | `reaction_layout.py:29-31` | **Medium** |
| R3 | Multi-step reactions (an entity that is both source and target of different relations — an intermediate) raise `NotImplementedError`. Multi-step belongs in `pathway_layout.py`. | `reaction_layout.py:32-34` | **Low** (route to pathway is the official answer) |
| R4 | Per-molecule annotations / compound numbers. Deferred to a v2 `reaction_layout` that decomposes into per-molecule `LayoutEntry` items, paired with `label_placement`. | `reaction_layout.py:35-37, 165` | **Medium** |
| R5 | Per-arrow conditions in multi-step reactions (different conditions per arrow). v1 uses the first relation's conditions. | `reaction_layout.py:109` | **Low** |

### Primitives

| # | Item | Source | Priority |
|---|---|---|---|
| P1 | True 3D ball-and-stick chemistry rendering. v1's `style="ball_stick"` is still 2D — larger atom labels and wider bonds, visually leaning toward 3D. | `chemistry.py:8`; `phase2-step6-chemistry.md` | **Low** |
| P2 | Bond-line packing fixes for crowded chemistry diagrams. Deferred to Phase 6 (verification suite). | `chemistry.py:12` | **Low** |
| P3 | `_centered_label` helper currently lives in `proteins.py` and is imported across modules. Promote to a shared `primitives/_text.py` (or fold into Phase 4 style loader). | implicit in `label_placement._label_primitive`'s reuse | **Low** |

### Styles (Phase 4 deferrals)

| # | Item | Source | Priority |
|---|---|---|---|
| ST1 | Auto-derive primitive fills from palette indices. A "recipe" layer that maps `palette[0] → protein_fill`, `palette[1] → kinase_fill`, etc. Reduces preset duplication; requires opinionated palette-to-primitive mappings. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST2 | Lift aesthetic layout-params (`pathway_band_fill`, `panel_border_stroke`, `panel_title_size`, etc.) into presets. Currently caller-set; a future preset could carry a `layout_overrides` block. | `phase4-style-presets.md` §Out of Scope | **Medium** |
| ST3 | Style preset *inheritance*. ACS could declare `inherits: "cell_press"` and override only chemistry. v1 has no inheritance — each preset is self-contained. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST4 | Per-figure style switching mid-render. v1 assumes one preset per `render_figure` call. | `phase4-style-presets.md` §Out of Scope | **Low** |
| ST5 | Style validation against the *full* primitive key set. The loader could collect every primitive's `DEFAULT_STYLE` keys at import time and warn if a preset references unknown keys (typo guard). | `phase4-style-presets.md` §Out of Scope | **Medium** |

---

## 3. Stretch (post-v1)

From `ROADMAP.md` §Stretch Goals and the master plan's "Stretch Goals"
section:

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

When starting v2 work, scan the relevant bucket for items to lift.
When you discover a new "out of scope" decision, add a row here in the
same shape — don't bury it in module docstrings alone.
