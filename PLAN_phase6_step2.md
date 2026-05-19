# Plan — Phase 6 Step 2: `verify/legibility_check.py`

## Pre-flight (done)

- `pytest tests/` → **328 passed**.
- Step 1 shipped: `verify/semantic_check.py` (108 lines) + `tests/test_verify_semantic.py` (9 tests) are green.
- `verify/legibility_check.py` exists but is **empty (0 lines)** — Step 2 is genuinely unstarted.
- TODO.txt `IN PROGRESS:` correctly points at Step 2. **Not stale — no update needed.**

## Step restated

Build an after-the-fact audit of text legibility in a rendered figure:

1. **Overlap check** — no two text-label bounding boxes may overlap.
2. **Font-size check** — no label may render below a minimum readable size.
3. **Crop signal** — return a flag to Step 3 indicating whether the figure
   has excess whitespace and would benefit from an intelligent zoom/crop.

The label-placement engine already avoids overlap *at placement time*, but the
compositor stacks layers independently; this is the independent audit.

---

## Design decisions (please confirm / edit)

### D-A. Operate on the rendered SVG, not IR + LayoutEntry — **propose: SVG**
Mirrors `semantic_check`. The rendered `<text>` element is the only place the
*final composed* position and font-size exist together; LayoutEntry positions
are pre-compositor and would miss exactly the layer-stacking bugs this check
targets. Confirmed by TODO.txt's own open-question note.

A rendered `<text>` looks like:
```
<text dominant-baseline="central" fill="#1A1A1A"
      font-family="Helvetica, Arial, sans-serif" font-size="11.0"
      text-anchor="middle" x="760.0" y="300.0">Ras</text>
```
So `font-size`, `text-anchor`, `dominant-baseline`, `x`, `y`, and the text
content are all available by parsing with `ElementTree` (same as Step 1).

### D-B. Bbox derivation — reuse `label_placement` helpers, no reimplementation
SVG `<text>` carries no intrinsic bbox. We re-derive it:
- width/height from `_estimate_text_bbox(text, font_size)` (existing heuristic).
- `x`/`y` is an *anchor point*, not a corner. Convert to a corner-box using
  `text-anchor` (`start`/`middle`/`end`) and `dominant-baseline`
  (`central` → y is vertical center; else y is the baseline).
- For the common `middle` + `central` case this is exactly
  `_bbox_from_center((x, y), size)` — also already in `label_placement.py`.

Reused as-is (all underscore-private, imported directly):
`_estimate_text_bbox`, `_overlaps`, `_bbox_from_center`, and the `Bbox` alias
(`tuple[float, float, float, float]`). Nothing re-implemented.

### D-C. **API surprise — flagging per workflow lesson #5**
`semantic_check` is pure raise-on-first / returns `None`. Step 2 *cannot* be
pure raise-on-first, because it must **return** a crop flag to Step 3.

Proposed shape — the function does **both**:
- **Raises `LegibilityCheckError`** on the first hard failure (overlap or
  undersized font), mirroring `SemanticCheckError`.
- **Returns a `LegibilityResult` dataclass** when the figure is legible,
  carrying the crop signal.

```python
@dataclass(frozen=True)
class LegibilityResult:
    needs_crop: bool        # excess whitespace → Step 3 should zoom/crop
    content_bbox: Bbox      # union of all label bboxes
    canvas_bbox: Bbox       # (0, 0, svg_width, svg_height)

def legibility_check(
    svg_path: str | Path,
    *,
    min_font_size: float = 6.0,
    overlap_margin: float = 0.0,
    crop_whitespace_fraction: float = 0.15,
) -> LegibilityResult
```
Note `legibility_check` takes only `svg_path` — it needs no IR (unlike
`semantic_check(ir, svg_path)`), since every fact it audits is in the SVG.

### D-D. Minimum readable font size — **propose: fixed param default `6.0` pt**
Not pulled from the style preset. Presets vary and "minimum *readable*" is a
physical constant, not a stylistic one. A caller can still override per-call.

### D-E. Crop signal — **propose: text-bbox union as the v1 proxy** *(main open question)*
`content_bbox` = union of all label bboxes. `needs_crop` is `True` when the
whitespace margin on any side exceeds `crop_whitespace_fraction` of that
dimension. Step 3 owns the actual crop math; Step 2 only reports.

Limitation to accept or reject: labels sit *on* the subjects but graphics
(arrows, molecules) can extend beyond them, so the union slightly under-covers.
Options:
- **(v1, proposed)** text-bbox union only — simple, keeps Step 2 small.
- (alt) also union the extents of every `<g id=...>` group — needs per-group
  bbox, which SVG does not provide without a full geometry walk; larger scope.

I propose v1 and a one-line docstring note that Step 3 may refine.

### D-F. Check order
Font-size first (single pass over labels), then pairwise overlap. Raise-on-first
means a font failure pre-empts overlap reporting — consistent with `semantic_check`.

---

## `LegibilityCheckError` shape (mirrors `SemanticCheckError`)

```python
class LegibilityCheckError(RuntimeError):
    kind: Literal["overlap", "font_size"]
    labels: tuple[str, ...]   # offending text(s): 2 for overlap, 1 for font
    detail: str               # e.g. font size vs floor, or the two bboxes
    # human-readable message via super().__init__
```

---

## Implementation outline (`verify/legibility_check.py`, ~90–110 lines)

1. Module docstring — same style as `semantic_check.py` (scope + failure mode).
2. `_Kind = Literal["overlap", "font_size"]`; `LegibilityCheckError`.
3. `LegibilityResult` dataclass.
4. `_parse_labels(root)` → list of `(text, font_size, bbox)` from every `<text>`,
   converting anchor point → corner box via `text-anchor`/`dominant-baseline`.
5. `_canvas_bbox(root)` → `(0, 0, width, height)` from the `<svg>` attrs.
6. `legibility_check(svg_path, *, ...)`:
   - parse SVG with `ElementTree`,
   - font-size pass → raise `kind="font_size"`,
   - pairwise `_overlaps` → raise `kind="overlap"`,
   - union label bboxes → `needs_crop` → return `LegibilityResult`.

## Test plan — `tests/test_verify_legibility.py` (propose 6 tests)

Happy-path tests render real fixtures via `render_figure` (like Step 1).
Failure-mode tests use small **hand-written synthetic SVG fixtures** written to
`tmp_path` — deterministic, and far easier than coaxing a real render into a
known-bad state.

1. `test_pathway_figure_passes` — render `mapk_cascade.json`; returns a
   `LegibilityResult`, no raise.
2. `test_panel_figure_passes` — render `three_panel_workflow.json`; no raise.
3. `test_overlapping_labels_raise` — synthetic SVG, two `<text>` at the same
   coords → raises `LegibilityCheckError`, `kind == "overlap"`.
4. `test_undersized_font_raises` — synthetic SVG with `font-size="3"` → raises,
   `kind == "font_size"`.
5. `test_needs_crop_true` — synthetic SVG, one small label on a large canvas →
   `result.needs_crop is True`.
6. `test_needs_crop_false_and_exception_attrs` — dense synthetic SVG →
   `needs_crop is False`; plus assert the raised exception's `kind`/`labels`
   are populated and appear in `str(exc)`.

Expected count after Step 2: **328 + 6 = 334 green**.

## Commit cadence (workflow lesson #3 / #12 — three commits)

1. `docs(README)` — Phase 6 Step 2 row + test-count bump.
2. `feat(verify)` — `verify/legibility_check.py`.
3. `test(verify)` — `tests/test_verify_legibility.py`.

Then `/simplify` on the changed files **before** committing impl/tests
(lesson #10), and update `~/Desktop/TODO.txt` (move Step 2 → COMPLETED,
promote Step 3 into `IN PROGRESS:`).

## Open questions for you

- **D-C**: OK with `legibility_check` both raising *and* returning? (vs. e.g.
  a pure-return `LegibilityResult` that lists violations — diverges from Step 1).
- **D-E**: text-bbox-union v1 acceptable, or do you want graphics extents too?
- **D-D**: `6.0` pt floor reasonable, or a different number?
