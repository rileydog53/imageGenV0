# Plan: Entity label fitting (text-vs-box overflow)

## Context

Entity boxes are a fixed size per type (`ENTITY_BBOX`, `_geom.py:23` — e.g.
metabolite = 60×30px). The label is rendered dead-center via
`_text.centered_label()` with `text-anchor: middle` and is **never measured
against the box**. Any label longer than ~9 chars at the 11px default font
(`proteins.py:75`) spills past the box border — visible on TCA nodes like
"a-Ketoglutarate", "Oxaloacetate", "Succinyl-CoA", "Acetyl-CoA".

There is currently **no text-measurement step** anywhere in the layout/render
path — primitives emit SVG `<text>` and let the renderer lay it out blind.

## The fit ladder (escalation order)

For each entity label, apply the first rung that makes the text fit inside the
box (with a small inner padding, ~4px each side):

1. **Fits as-is** → render centered, no change. (rung 0)
2. **Wrap to 2 lines** → if the label has a natural break (space, `/`, or `-`),
   split into 2 lines and check both lines fit the width AND the stacked height
   fits the box. Render as a 2-line centered `<text>` (tspans).
3. **Shrink font** → scale font down toward a floor (e.g. 8px) until the
   widest line fits. Combine with rung 2 if needed.
4. **External label + leader** → if even the floor font overflows, render the
   box empty (or with a short ID) and place the full label *outside* the box
   with a thin leader line/arrow pointing back to it. Reuse the existing
   off-node label-placement machinery (`label_placement.py` already positions
   relation labels outside nodes — anchor a new entity-label request there).

## Where the measurement comes from

No real font metrics at layout time, so use the same pragmatic estimate the
rest of the engine would: approximate text width as
`n_chars * font_size * AVG_CHAR_RATIO` where `AVG_CHAR_RATIO ≈ 0.55` for the
sans default. Good enough to decide rungs; err slightly wide so we under-fill
rather than overflow.

Add a small helper, e.g. `_text.estimate_text_width(text, font_size, style)`
and `_text.fit_label(label, box_w, box_h, style) -> FitResult` where
`FitResult` carries `{lines: list[str], font_size: float, external: bool}`.

## Files to touch

| File | Change |
|---|---|
| `imageGen/primitives/_text.py` | Add `estimate_text_width()` + `fit_label()`; extend `centered_label()` (or add `multiline_label()`) to emit stacked tspans at a given font size |
| `imageGen/primitives/proteins.py` | `generic_protein()`, `kinase()`, `protein_complex()` call `fit_label()` and render rung 0–3; signal rung-4 (external) back to caller |
| `imageGen/layout/pathway_layout.py` | When a primitive reports rung-4, emit an entity-label request through the existing label-placement path (leader line) |
| `imageGen/primitives/_text.py` (tests) | unit tests for `fit_label` rung selection |
| `tests/test_primitives_proteins.py` | assert long labels wrap/shrink, very long labels go external |

## Verification

1. `pytest tests/ -q` stays green.
2. New unit tests: short label → rung 0; "a-Ketoglutarate" → rung 2/3 (wrapped
   or shrunk, no overflow); a pathological 30-char label → rung 4 (external).
3. Manual: re-render the 8-node TCA (`scratch/tca_skillready2.yaml`) and
   confirm every node label sits inside its box, with any unfittable label
   pushed outside on a leader.

## Scope guard (keep it simple)

- Don't auto-grow boxes — that reflows the whole ring/DAG geometry. Fit the
  text to the box, not the box to the text. (A future option could grow
  `ENTITY_BBOX` per-figure, but that's out of scope here.)
- Rung 4 (external) should be rare; it's the safety net, not the default.
