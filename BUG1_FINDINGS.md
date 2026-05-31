# Bug 1 — confirmed root cause (arrows render inside / backwards in boxes)

## Symptom
In `stress3_longlabels`, the tissue→facs and lib→seq arrows render as a tiny
backwards arrowhead *inside* a box. Looks like "two entities in one box."

## Root cause (confirmed by arithmetic, not theory)

The LT4 label-extent x-clamp in `_graph_positions`
(`pathway_layout.py:857-858` layered branch, `:880-881` even-spacing branch):

```python
half_x = max(ew, _label_extent_w(e.label)) / 2
x = _clamp_center_x(x, ox + edge_margin, ox + w - edge_margin, half_x)
```

clamps each entity's center so its **centered-label footprint** stays on canvas.

For stress3: canvas_w=800, inner_w=720, ranks 0..6, so layered x = 40 + 120·rank:

| entity | rank | x (pre-clamp) | label chars | half_x | x (post-clamp) |
|--------|------|---------------|-------------|--------|----------------|
| tissue | 0 | 40  | 35 | 115 | **123** (pushed right) |
| facs   | 1 | 160 | 35 | 115 | 160 |
| cells  | 2 | 280 | 31 | 102 | 280 |
| rt     | 3 | 400 | — | — | 400 |
| cdna   | 4 | 520 | — | — | 520 |
| lib    | 5 | 640 | 41 | 135 | 640 |
| seq    | 6 | 760 | 43 | 142 | **650** (pushed left) |

- tissue clamped 40→123 → box [93,153]; facs box [130,190] → **overlap 23px**.
- seq clamped 760→650 → box [620,680]; lib box [610,670] → **overlap 50px**.

These exactly match the rendered SVG box coordinates.

When source/target boxes overlap, `_arrow_endpoints` / `_bbox_exit_point`
produce inverted exit points → the connecting arrow draws backwards with its
head inside a box. That is the visible artifact.

## Why this is now a bug (it wasn't when LT4 shipped)

LT4 was a pre-fit-ladder workaround: it reserved horizontal room for labels
that would otherwise render centered-and-overflowing past the canvas edge.

Since the label-fit ladder landed, that premise is gone:
- rung 0–3: the label is wrapped/shrunk to fit **inside the 60px box** — it
  never extends ±115px, so reserving that space is pointless.
- rung 4: the label is **external**, placed by `place_labels` (which already
  respects canvas bounds) — it is not centered on the box, so reserving
  centered space for it is simply wrong.

In every case the centered-label clamp is obsolete, and here it actively
forces box overlap.

## The mechanism is general, not stress3-specific
Any pathway where two adjacent-rank entities both carry labels wider than the
inter-rank spacing will collide the same way. This is the "arrows fail on
complicated entities" the user observed.

## Recommended fix (Option A)
Retire the label-extent term from the two position clamps — clamp by box width
only:

```python
half_x = ew / 2
x = _clamp_center_x(x, ox + edge_margin, ox + w - edge_margin, half_x)
```

Keeps boxes on canvas; lets the fit ladder + bounds-aware label engine own
label-vs-canvas. `_clamp_center_x` itself is unchanged (its own unit tests at
test_layout_pathway.py:218,229 stay green).

### Implications
- `test_wide_label_entity_stays_within_narrow_canvas` (test_layout_pathway.py:237)
  encodes the obsolete LT4 position behavior — must be updated to assert the
  **box** stays in canvas (the label is now fit/externalized).
- Golden churn: any pathway figure with a label wider than its box may shift.
  Re-render and eyeball before regenerating goldens.

## Alternatives considered
- **B (widen canvas to fit end-node labels):** "more correct" but grows many
  figures and churns more goldens; heavier change.
- **C (min-spacing post-pass):** robust but can re-push nodes off-canvas;
  more code than A.
