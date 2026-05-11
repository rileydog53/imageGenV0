"""Greedy automated label placement.

Phase 3 Step 4. A pure, IR-agnostic post-pass: callers hand a list of
positioned `LayoutEntry` items (from any layout engine) plus a list of
`LabelRequest` records, and the engine returns the original entries with
new label `LayoutEntry` items appended in placement order. The Phase 5
renderer composes both lists by simply executing them.

Decoupling:
  Layout engines (`pathway_layout`, `panel_layout`, …) do not auto-invoke
  this module. Each engine that wants to render labels exposes a sibling
  helper that walks its IR shape and emits `LabelRequest` records;
  see `pathway_layout.pathway_label_requests` for the canonical example.
  This keeps the placement engine generic — it never imports IR types.

Algorithm:
  Greedy. For each request in submission order, evaluate candidate
  positions in the request's `priority` tuple ("right", "below",
  "above", "left", "center"). Pick the first candidate whose label bbox
  doesn't overlap any *known-bbox* entry from the input list, nor any
  previously placed label. If every candidate overlaps, accumulate into
  a failure list and raise `LabelPlacementError` at the end so partial
  work is visible.

  Force-directed placement is a v2 stretch — flagged in the SKILL plan.

Bbox sources:
  - Entity entries: looked up via `_ENTITY_BBOX` from `pathway_layout`
    (a small per-`EntityType` table). Cross-module import is private but
    documented; promoting `_ENTITY_BBOX` to a shared `layout/_geom.py`
    is a deferred cleanup flagged in `~/Desktop/TODO.txt`.
  - Compartment bands and panel chrome: treated as no-bbox. These
    primitives are full-width decorative backgrounds, not obstructions —
    labels are expected to render on top of them. Including them would
    block every candidate position because they span the entire canvas.
  - Other primitives (arrows, label primitives, etc.): also no-bbox.
    Arrows are thin shafts; allowing label-on-shaft overlap in v1 keeps
    the engine simple. Phase 6 `legibility_check` will surface any
    visible problem.

  Label bboxes are estimated from text length × font size with a fixed
  width-to-height aspect (no font-metric library at this stage; svgwrite
  has no measurement API). The estimator is monotonic in both inputs and
  has an explicit unit test.

Phase 4 / 5 coupling:
  - `DEFAULT_LAYOUT_PARAMS` keys use the `label_*` prefix so the master
    preset can union them alongside primitive `DEFAULT_STYLE` dicts
    without collision (matches the convention in `pathway_layout`,
    `panel_layout`, etc.).
  - Label `LayoutEntry` items use `position=(0.0, 0.0)`; the absolute
    SVG coordinates are baked into the args, mirroring how
    `pathway_layout` emits its entity entries. The renderer's
    `translate(position)` is a no-op for these.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import svgwrite.container

from layout.types import LayoutEntry
from primitives import proteins


# ---------------------------------------------------------------------------
# Layout knobs (flat namespaced keys; Phase 4 master preset will union these
# alongside primitive DEFAULT_STYLE dicts).
# ---------------------------------------------------------------------------

DEFAULT_LAYOUT_PARAMS: dict[str, Any] = {
    "label_anchor_gap":        4.0,   # px between anchor bbox and label bbox
    "label_collision_margin":  1.0,   # px slack when testing overlap
}


_VALID_PRIORITIES: tuple[str, ...] = ("right", "below", "above", "left", "center")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LabelRequest:
    """One label to place near an anchor.

    Attributes:
        text: The label string.
        anchor: (x, y) center the label should sit near (e.g., the
            midpoint of a relation arrow, or the center of an entity).
        anchor_size: (w, h) bbox of the anchor itself; the label is
            offset by half this plus `label_anchor_gap` along the chosen
            direction so it doesn't sit on top of the anchor.
        priority: Ordered tuple of candidate-position names tried in
            sequence. Each must be in
            {"right", "below", "above", "left", "center"}.
    """
    text: str
    anchor: tuple[float, float]
    anchor_size: tuple[float, float]
    priority: tuple[str, ...] = _VALID_PRIORITIES

    def __post_init__(self) -> None:
        unknown = [p for p in self.priority if p not in _VALID_PRIORITIES]
        if unknown:
            raise ValueError(
                f"LabelRequest.priority contains unknown name(s) {unknown!r}; "
                f"allowed values: {list(_VALID_PRIORITIES)}"
            )


class LabelPlacementError(RuntimeError):
    """Raised when one or more LabelRequests cannot be placed without overlap.

    The `failures` attribute is a list of the LabelRequest items that
    could not be placed at any priority. Successful placements before
    the failure are still returned in `entries` for inspection.
    """

    def __init__(
        self,
        failures: list[LabelRequest],
        entries: list[LayoutEntry],
    ) -> None:
        self.failures = failures
        self.entries = entries
        texts = ", ".join(repr(f.text) for f in failures)
        super().__init__(
            f"Could not place {len(failures)} label(s) without overlap: {texts}"
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# (label, x, y, w, h) → axis-aligned bbox (x0, y0, x1, y1)
Bbox = tuple[float, float, float, float]


def _estimate_text_bbox(text: str, font_size: float) -> tuple[float, float]:
    """Estimate (width, height) for `text` at `font_size`.

    Uses font_size * char_count * 0.6 for width, font_size * 1.2 for
    height. Sans-serif characters average ~0.6 em wide; line-height is
    conventionally ~1.2x font size. Good enough for collision checks at
    v1 — Phase 6 `legibility_check` validates final output independently.
    """
    return (max(1, len(text)) * font_size * 0.6, font_size * 1.2)


def _candidate_center(
    name: str,
    anchor: tuple[float, float],
    anchor_size: tuple[float, float],
    label_size: tuple[float, float],
    gap: float,
) -> tuple[float, float]:
    """Compute the (x, y) center of a candidate label bbox by direction name."""
    ax, ay = anchor
    aw, ah = anchor_size
    lw, lh = label_size
    if name == "right":
        return (ax + aw / 2 + gap + lw / 2, ay)
    if name == "left":
        return (ax - aw / 2 - gap - lw / 2, ay)
    if name == "above":
        return (ax, ay - ah / 2 - gap - lh / 2)
    if name == "below":
        return (ax, ay + ah / 2 + gap + lh / 2)
    if name == "center":
        return (ax, ay)
    raise ValueError(f"unknown candidate name {name!r}")  # validated upstream


def _bbox_from_center(center: tuple[float, float], size: tuple[float, float]) -> Bbox:
    cx, cy = center
    w, h = size
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _overlaps(a: Bbox, b: Bbox, margin: float) -> bool:
    """Axis-aligned bbox overlap with a small `margin` of slack."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (
        ax0 < bx1 + margin
        and ax1 + margin > bx0
        and ay0 < by1 + margin
        and ay1 + margin > by0
    )


_ENTITY_PRIMITIVES: frozenset = frozenset({
    proteins.generic_protein,
    proteins.kinase,
    proteins.receptor,
    proteins.gpcr,
    proteins.transcription_factor,
})


def _entry_bbox(entry: LayoutEntry) -> Bbox | None:
    """Best-effort bbox extraction for a positioned LayoutEntry.

    Only entity primitives contribute a collision bbox. Compartment
    bands and panel chrome span the full canvas / cell and are treated
    as decorative backgrounds (see module docstring). Arrows, labels,
    and any other unknown primitives return None.
    """
    if entry.primitive not in _ENTITY_PRIMITIVES:
        return None
    # entity-primitive args: (label, (cx, cy), ...) per pathway_layout
    _, center = entry.args[:2]
    cx, cy = center
    # Reverse-lookup the bbox via the per-EntityType table. Multiple
    # EntityTypes can share a primitive — pick the largest bbox among
    # them so collision checks stay conservative. Lazy import breaks the
    # `pathway_layout → label_placement` cycle for `pathway_label_requests`.
    from layout import pathway_layout  # noqa: PLC0415
    candidates = [
        pathway_layout._ENTITY_BBOX[t]
        for t, p in pathway_layout.ENTITY_TO_PRIMITIVE.items()
        if p is entry.primitive
    ]
    if not candidates:
        return None
    w = max(c[0] for c in candidates)
    h = max(c[1] for c in candidates)
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


_DEFAULT_LABEL_STYLE: dict = {
    "label_font_family": "Helvetica, Arial, sans-serif",
    "label_font_size": 11,
    "label_font_color": "#1A1A1A",
}


def _label_primitive(
    text: str,
    center: tuple[float, float],
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a single label as a centered Text wrapped in a Group.

    Delegates the Text construction to `proteins._centered_label`, the
    established label-text contract for this codebase, so Phase 4
    master-preset `label_*` keys flow through one helper.
    """
    style = {**_DEFAULT_LABEL_STYLE, **(style_dict or {})}
    cx, cy = center
    g = svgwrite.container.Group()
    g.add(proteins._centered_label(text, cx, cy, style))
    return g


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def place_labels(
    entries: list[LayoutEntry],
    label_requests: list[LabelRequest],
    layout_params: dict | None = None,
    style_dict: dict | None = None,
) -> list[LayoutEntry]:
    """Greedily place each LabelRequest near its anchor without overlap.

    Args:
        entries: Positioned LayoutEntry items from a layout engine.
            Returned unchanged at the head of the result.
        label_requests: Labels to place. Processed in submission order;
            earlier requests reserve space first.
        layout_params: Optional overlay onto `DEFAULT_LAYOUT_PARAMS`.
            Notable keys: `label_anchor_gap`, `label_collision_margin`.
        style_dict: Optional preset overlay forwarded to every emitted
            label primitive. The font size from this dict (if any) is
            also used for the bbox estimator so the collision check
            matches what will render.

    Returns:
        `entries` followed by one new LayoutEntry per successfully placed
        label. Each label entry has `position=(0.0, 0.0)`; coordinates
        are baked into args for renderer uniformity.

    Raises:
        LabelPlacementError: One or more requests had no non-overlapping
            candidate position. The exception carries the failed
            requests and the partial entry list.

    The placement order matches the order of `label_requests`: earlier
    labels claim space before later ones evaluate it.
    """
    params = {**DEFAULT_LAYOUT_PARAMS, **(layout_params or {})}
    gap = float(params["label_anchor_gap"])
    margin = float(params["label_collision_margin"])
    font_size = float((style_dict or {}).get("label_font_size", 11))

    occupied: list[Bbox] = [
        bbox for bbox in (_entry_bbox(e) for e in entries) if bbox is not None
    ]

    label_kwargs: dict = {"style_dict": style_dict} if style_dict is not None else {}
    out: list[LayoutEntry] = list(entries)
    failures: list[LabelRequest] = []

    for request in label_requests:
        label_size = _estimate_text_bbox(request.text, font_size)
        placed = False
        for name in request.priority:
            center = _candidate_center(
                name, request.anchor, request.anchor_size, label_size, gap
            )
            candidate_bbox = _bbox_from_center(center, label_size)
            if any(_overlaps(candidate_bbox, b, margin) for b in occupied):
                continue
            out.append(LayoutEntry(
                primitive=_label_primitive,
                args=(request.text, center),
                kwargs=label_kwargs,
                position=(0.0, 0.0),
            ))
            occupied.append(candidate_bbox)
            placed = True
            break
        if not placed:
            failures.append(request)

    if failures:
        raise LabelPlacementError(failures=failures, entries=out)
    return out
