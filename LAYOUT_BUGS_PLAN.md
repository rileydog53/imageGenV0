# Layout defects — top-down plan

Observed across six test figures rendered 2026-05-30. The individual symptoms
are different but they share a single root: the three pipeline stages (entity
placement, arrow routing, label placement) are blind to each other's output.
Each fix below addresses a specific symptom, but all of them flow from the
same architectural gap.

---

## Architectural gap (root of everything)

The pipeline today is effectively three separate passes that barely share
information:

```
Pass 1 — layout_pathway()
    positions every entity, routes every arrow shaft
    output: LayoutEntry list (entity primitives + arrow primitives)

Pass 2 — place_labels()
    places relation labels and entity external labels
    knows: entity body bboxes
    blind to: arrow shaft positions, entity label extents

Pass 3 — compositor
    renders LayoutEntry items in order
    knows: nothing; just executes
```

Because Pass 2 cannot see arrow shafts, labels land on arrows.
Because Pass 1 cannot see label extents, arrows route through labels.
Because Pass 1 uses body-only bboxes as exit points, arrow endpoints can
land inside entity boxes when anything about the entity departs from the
simple rectangular model (external labels, side-label primitives like
receptor, non-rectangular glyphs).

The fix is not to rewrite the pipeline — it is to make each pass share
the footprint information the next pass needs. Two concrete additions:

  A. Arrow shafts → Pass 2.  Before calling `place_labels`, build a list
     of `shaft_bboxes` from every arrow LayoutEntry and add them to the
     `occupied` set. Labels will no longer be placed on arrow lines.

  B. Label extents → Pass 1.  After an entity's label is fit (fit_label),
     record its full footprint (body bbox ∪ label bbox) and use THAT for
     `_bbox_exit_point`, not just the body bbox.

Every bug below is either fixed by A, fixed by B, or is a specific
misclassification in the routing or label-fit logic that can be fixed in
isolation once A and B are in place.

---

## Bug 1 — Arrow endpoints land INSIDE entity boxes (stress3)

**What you see:** The tissue box and the lib box each have a left-pointing
arrowhead artifact rendered inside the box body. These are relation arrows
whose start or end point was computed to be inside the entity bbox rather
than at its edge.

**Root cause:**
`_bbox_exit_point` computes where the line from entity-center toward the
target exits the entity's rectangular bbox. For entities whose labels went
external (rung-4), the entity is still positioned at the same center, but
something about the effective_bbox or position passed to `_arrow_endpoints`
disagrees with what was used at render time.

Most likely: in `layout_pathway`, when an external-label entity is emitted,
the `size=` kwarg passed to the primitive is the raw `effective_bbox` (body
only). `_arrow_endpoints` also uses `effective_bbox`. These agree. BUT if
the external-label implementation changed `size` to something else (e.g.
zero or reduced) to make the box "empty", then the two diverge — routing
exits at a point that doesn't match the rendered box edge, placing the
arrowhead inside the visible rect.

**Fix (highest priority — shapes the other fixes):**
1. Audit: add a temporary `assert` in `layout_pathway` that the `size`
   passed to `_entry(override_prim, args, kwargs)` for external-label
   entities exactly matches the `effective_bbox` used in `_arrow_endpoints`
   for the same entity. If this fires, that's the bug.
2. Ensure external-label entities pass the full body `effective_bbox` to
   both the primitive render call AND `_arrow_endpoints`. The fact that
   the label is external must not change the body size.
3. Once confirmed fixed, remove the assert.

**Files:** `imageGen/layout/pathway_layout.py`

---

## Bug 2 — Relation labels land on arrow shafts (safe1, stress2)

**What you see:**
- safe1: "EGFR" is strikethrough'd by the binding arrow shaft.
- stress2: "Ser15", "ubiquitinate", "feedback" all sit on or immediately
  beside arrow shafts running through the same region.

**Root cause:** Architectural gap A (above). `place_labels` has no knowledge
of where arrow shafts are. Arrow shafts are thin and currently treated as
zero-footprint by the placement engine (module docstring calls this out as a
known v1 limitation).

**Fix:**
In `pathway_layout.layout_pathway` (or a new helper called just before
`place_labels`), build a shaft_bbox for every arrow LayoutEntry:

```python
def _shaft_bbox(entry: LayoutEntry) -> Bbox | None:
    """Thin axis-aligned bbox along an arrow shaft for label-placement collision."""
    # entry.args = (start, end); entry.kwargs may have 'waypoints'
    if entry.primitive not in RELATION_TO_ARROW.values():
        return None
    pts = entry.kwargs.get("waypoints") or list(entry.args[:2])
    # bounding box of all waypoints, expanded by SHAFT_HALF_WIDTH each side
    SHAFT_HALF_WIDTH = 6.0   # px — wide enough to give labels a gap
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs) - SHAFT_HALF_WIDTH, min(ys) - SHAFT_HALF_WIDTH,
            max(xs) + SHAFT_HALF_WIDTH, max(ys) + SHAFT_HALF_WIDTH)
```

Pass the resulting list as `extra_occupied` to `place_labels()`, which adds
them to the greedy engine's `occupied` set before placing any label.

Note: for a multi-waypoint elbow arrow, the bbox of all waypoints is a
conservative rectangle that may be larger than the actual shaft. That is
acceptable — it errs toward labels avoiding arrows, which is the right
failure mode.

**Files:** `imageGen/layout/pathway_layout.py` (shaft_bbox helper + call),
`imageGen/layout/label_placement.py` (accept `extra_occupied` kwarg).

---

## Bug 3 — Receptor label overlaps arrows (safe1)

**What you see:** "EGFR" text is rendered to the LEFT of the receptor
hourglass body (that is how `receptor()` places it), and the bidirectional
binding arrow between EGF and EGFR passes straight through the text.

**Root cause:** Architectural gap B (above) specifically for the receptor
primitive. `receptor()` places its label to the left using `text-anchor: end`
(proteins.py:334). `ENTITY_BBOX[RECEPTOR] = (28, 60)` covers only the body.
Arrow routing exits the body at its left edge and proceeds toward EGF, passing
through where the label sits. The label is invisible to routing because only
the body bbox is in `ENTITY_BBOX`.

**Fix (two parts):**
1. In `label_placement._entry_bbox()`, detect receptor entries specifically
   (by checking `entry.primitive is proteins.receptor`) and extend the
   collision bbox leftward by the estimated label width. This is the same
   pattern already used for entity-label-extent widening (line 258).
2. In `pathway_layout._arrow_endpoints` (or `_bbox_exit_point`), use the
   extended footprint (body + label) as the effective half-widths when
   computing the exit point for receptor entities. Concretely: pass
   `half_w = body_w/2 + label_est_w` to `_bbox_exit_point` for receptor
   source/target entities.

A longer-term option: move the receptor label to above/below the body (where
gpcr places its label) so it never conflicts with horizontal arrows. Keep
that for a separate PR — the fix above is narrower and safe.

**Files:** `imageGen/layout/label_placement.py` (`_entry_bbox`),
`imageGen/layout/pathway_layout.py` (`_arrow_endpoints`).

---

## Bug 4 — Same-band skip arrow classified as cross-band (stress2)

**What you see:** The ATM → p53 direct phosphorylation arrow draws a flat
horizontal line across the top of the figure, passing directly over CHK2.
An arch should have fired but didn't.

**Root cause:**
In `layout_pathway`, the cross-band guard is:
```python
if location_map[r.source] != location_map[r.target]:
    wps = _orthogonal_waypoints(...)   # cross-band corridor path
else:
    wps = same_band_routes.get(idx)    # None → straight, or arch
```
Both ATM and p53 are in the single implicit band, so this guard should be
False and the arrow should go through `same_band_routes`. But `same_band_routes`
is only populated for entries where `location_map[r.source] ==
location_map[r.target]` — and if `_route_same_band_arrows` itself uses
`location_map` to filter, both checks should agree.

The likely actual bug: `_segment_hits_rect` returns False for ATM→p53 because
the layered DAG placed CHK2 at a different y than ATM and p53, so the straight
shaft truly misses CHK2's bbox in the math — even though visually the shaft
runs through CHK2's rendered area. This happens when entities in the same
implicit band are spread vertically by the L20 topo-y logic.

**Fix:**
1. In `_route_same_band_arrows`, broaden the hit-test margin from 0 to 8px:
   `_segment_hits_rect(start, end, ocx, ocy, ow/2 + 8, oh/2 + 8)`. This
   catches near-misses where the shaft grazes an entity bbox visually but
   misses it mathematically.
2. After fix (1), also check against the label footprint (body + estimated
   label extent), not just the body — so a shaft that misses the body but
   passes through a long label also arches.

**Files:** `imageGen/layout/pathway_layout.py` (`_route_same_band_arrows`).

---

## Bug 5 — External-label boxes have no leader lines (stress3)

**What you see:** Rung-4 entity boxes are empty blue rectangles. Their label
text floats above/below with no visual connection back to the box.
Additionally, entity external labels and relation labels compete for the same
slot (e.g. "Fluorescence-activated cell sorting" and "load onto sorter" stack
on top of each other above the FACS box).

**Root cause:**
The rung-4 implementation emits a LabelRequest but no leader-line primitive.
The LABEL_FIT_PLAN said "leader line/arrow pointing back to it" — the request
was wired but the line was not drawn.

Secondary: entity external labels enter `place_labels()` mixed with relation
labels, so both compete equally for the slot nearest the box.

**Fix:**
1. After `place_labels()` resolves all external-label positions, walk the
   result looking for `_extlabel` entries. For each one, emit a thin
   `svgwrite.path.Path` from the label center to the nearest edge of the
   entity body bbox (a short dashed line, 0.5px, `label_font_color`).
2. Feed entity external-label requests to `place_labels()` in a FIRST batch
   (before relation label requests), so they claim the nearest slot to their
   own box before relation labels do. Relation labels, which can roam the full
   canvas, should yield to the entity they are adjacent to.

**Files:** `imageGen/layout/pathway_layout.py` (leader-line emit, label-request
ordering).

---

## Bug 6 — Ring label crowding + bad wrap (stress1)

**What you see:** "SDH" and "SCS" are jammed beside "Succinate" at the bottom
of the Krebs ring. "a-Ketoglutarate" wraps to "a-" / "Ketoglutarate" — a
two-char first fragment that looks unbalanced.

**Root cause (crowding):**
The radial outward nudge is 14px (`pathway_label_requests`). At the bottom of
the ring, two adjacent chords (Succinyl-CoA→Succinate and Succinate→Fumarate)
converge near the same radial angle, so their 14px-nudged anchors are nearly
co-located. The greedy engine separates them but by barely more than 1px.

**Root cause (wrap):**
`fit_label()` tries breaks in order of position and accepts the FIRST break
that makes both lines fit. For "a-Ketoglutarate" the first break is at the
hyphen after "a", yielding "a-" (2 chars) + "Ketoglutarate" (13 chars).
There is no heuristic to prefer balanced splits.

**Fix (crowding):**
Increase the ring radial nudge to 24px. For adjacent chord pairs whose
nudged anchors are within 20px of each other, apply an additional divergence
push of ±12px perpendicular to the radial direction so the two labels fan
apart rather than colliding.

**Fix (wrap balance):**
In `fit_label()`, when evaluating wrap break candidates, skip any break that
leaves a first fragment shorter than 3 characters — unless it is the ONLY
available break. For "a-Ketoglutarate" this skips the "a-" break, finds no
other break, and falls through to the shrink rung (which fits the full label
at a smaller font) — a better result than the lopsided split.

**Files:** `imageGen/layout/pathway_layout.py` (`pathway_label_requests`),
`imageGen/primitives/_text.py` (`fit_label`).

---

## Execution order

Run in this order to minimize golden churn:

| Step | Bug | Risk | Notes |
|------|-----|------|-------|
| 1 | Bug 6 wrap balance | Low — only `_text.py` | Pure logic change, existing tests cover it |
| 2 | Bug 1 endpoint audit | Low — assert then remove | Confirms root cause before other fixes land |
| 3 | Bug 3 receptor footprint | Low — additive | Extend bbox in two places, new test |
| 4 | Bug 2 shaft bbox → `place_labels` | Medium — changes label positions | May shift labels in ALL figures; run full suite, expect some golden churn |
| 5 | Bug 4 hit-test margin | Medium — changes arch routing | Test with stress2 hub; check no regressions in ring figures |
| 6 | Bug 5 leader lines + label ordering | Medium — visual change | Regen goldens for any figure with external-label entities |
| 7 | Bug 6 ring nudge | Low — ring figures only | Regen krebs / ring goldens after visual inspection |

## Scope guard

- Do NOT grow entity boxes or reflow positions.
- Do NOT add a font-metrics library — estimate-based width is sufficient.
- Bugs 2 and 4 together (shaft bbox + hit-test margin) will shift label
  positions across many existing figures. Run the full test suite, visually
  inspect any golden that changes, and regen only after approval.
- The receptor label relocation (moving it above/below instead of to the
  left) is explicitly out of scope for this plan — file as a separate ticket.
