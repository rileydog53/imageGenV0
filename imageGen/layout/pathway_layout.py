"""Pathway layout engine.

Translates an IR `Figure` whose `archetype == PATHWAY` into a list of
`LayoutEntry` tuples that the Phase 5 renderer consumes. Pathway figures
group entities into horizontal compartment bands (extracellular →
membrane → cytoplasm → nucleus per biological convention), place
entities within bands using a seeded NetworkX spring layout, and connect
them with arrows whose primitive is selected by `RelationType`.

LayoutEntry is reused from `layout.reaction_layout` for renderer
uniformity. When more layout engines need it, promote LayoutEntry to
`layout/__init__.py`.

Compartment ordering:
  Reads the declaration order from `figure.compartments`. If empty
  (e.g., a cascade with no spatial context like the MAPK fixture), a
  single implicit band is synthesized so downstream code is uniform.

Entity → primitive dispatch:
  `ENTITY_TO_PRIMITIVE[entity.type]`. Layout owns this policy so
  `entity.style` stays reserved for visual presets.

Relation → arrow dispatch:
  `RELATION_TO_ARROW[relation.type]`. PHOSPHORYLATES, TRANSCRIBES, and
  GENERIC all currently route to `activation_arrow`; the per-arrow
  annotation glyph (e.g. a "P" badge for phosphorylation) is deferred
  to Step 4 (`label_placement.py`).

v1 limitations (explicit gaps; not oversights):
  - Arrows are always straight lines from entity-center to entity-center.
    No crossing detection, no curving heuristic, no edge-anchored
    endpoints. Force-directed routing is a Phase 3+ stretch.
  - Entities within a band are ordered by their spring_layout x and
    then evenly spaced horizontally; the y is fixed to the band center
    rather than using spring_layout y (compartment containment).
  - Per-entity primitive sizing uses primitive defaults; pathway
    layout does not forward a `size` kwarg. Wire this up alongside
    Phase 4 style presets.
  - GENE entities map to `generic_protein` rather than a nucleic_acids
    helix; can be lifted to nucleic_acids primitives in a v2.
  - Compartment bands are simple coloured rects + a label. Dedicated
    organelle outlines (membrane, nuclear envelope) belong in archetype
    code, not the layout engine.

Phase 5 coupling:
  All emitted LayoutEntry items use `position=(0.0, 0.0)` because
  primitives are called with absolute SVG coordinates already baked in
  via the `position` arg (entities) or the `start`/`end` args (arrows).
  The renderer's translate(LayoutEntry.position) is therefore a no-op
  here; it stays in the contract for future engines that emit relative
  primitives.
"""
from __future__ import annotations

from typing import Any, Callable

import networkx as nx
import svgwrite.container
import svgwrite.path
import svgwrite.shapes
import svgwrite.text

from imageGen.ir.schema import (
    Archetype,
    Compartment,
    CompartmentType,
    Entity,
    EntityType,
    Figure,
    RelationType,
)
from imageGen.layout._geom import ENTITY_BBOX, ENTITY_TO_PRIMITIVE, max_entity_bbox
from imageGen.layout.types import LayoutEntry
from imageGen.primitives import arrows
from imageGen.primitives._text import centered_label as _centered_label


# ---------------------------------------------------------------------------
# Layout knobs (Phase 4 master preset will union these alongside primitive
# DEFAULT_STYLE dicts; flat namespaced keys for predictable union).
# ---------------------------------------------------------------------------

PATHWAY_DEFAULT_PARAMS: dict[str, Any] = {
    "pathway_canvas":            (800.0, 600.0),    # (w, h) — also the min-size floor
    "pathway_origin":            (0.0, 0.0),        # top-left of canvas
    "pathway_band_padding":      40.0,              # horizontal padding inside band
    "pathway_seed":              42,                # NetworkX RNG seed
    "pathway_arrow_gap":         4.0,               # px between bbox edge and arrow tip
    "pathway_band_fill":         "#F7F9FB",
    "pathway_band_stroke":       "#C8D4DD",
    "pathway_band_stroke_width": 0.5,
    "pathway_band_label_color":  "#4A5C68",
    "pathway_band_label_size":   11,
    "pathway_band_label_family": "Helvetica, Arial, sans-serif",
    # Band-wrap knobs (V2). When a band has more entities than fit on one
    # row, _graph_positions wraps them onto additional rows. The compositor
    # reads these to grow the canvas accordingly.
    "pathway_max_per_row":       6,                 # entities per band row before wrap
    "pathway_row_v_gap":         16.0,              # px between wrapped rows in a band
    # V2 / L9: uniform scale factor applied to every entity's (w, h) at
    # render time. Scales bboxes used for arrow routing and row-height
    # calculation in lock-step with visual size, so figures stay consistent.
    # Default 1.0 → primitive defaults (byte-identical to V1 output).
    "pathway_entity_scale":      1.0,
    # V2 / L15: minimum clearance (px) between an entity's bbox edge and the
    # SVG canvas boundary. Centers are clamped after even-spacing so entities
    # near the canvas perimeter never render partially outside the viewport.
    "pathway_edge_margin":       8.0,
    # V2 / L1: same-band arrow routing. Adjacent same-band entities get a
    # straight arrow; a "skip" arrow whose straight shaft would cross an
    # intervening entity arches over (or under) the row instead. Overlapping
    # arches are stacked into distinct lanes so their corridors never collapse
    # onto one another. `arch_clearance` is the gap between the entity row and
    # the first lane; `arch_lane_gap` is the spacing between successive lanes.
    "pathway_arch_clearance":    12.0,
    "pathway_arch_lane_gap":     14.0,
}


# ---------------------------------------------------------------------------
# V2 / L3: dynamic band height helpers
# ---------------------------------------------------------------------------

_BAND_BASELINE = 100.0   # px — matches v1: 600 / 6 bands = 100 px/band
_LABEL_MARGIN  =  40.0   # px — headroom for band label + top/bottom breathing room


def _compute_band_heights(
    compartments: list[Compartment],
    by_band: dict[str, list],
    max_per_row: int,
    row_v_gap: float,
    max_entity_h: float,
) -> list[float]:
    """Return minimum pixel height for each compartment band (in declaration order).

    Each band receives enough vertical room for its wrapped entity rows plus a
    fixed label/margin allowance. Bands with no entities get the BAND_BASELINE
    floor so they don't collapse to zero. The BAND_BASELINE (100 px) matches
    the implicit per-band allocation in v1 (600 px ÷ 6 bands), so single-row
    figures produce the same geometry as before.
    """
    heights = []
    for c in compartments:
        ents = by_band.get(c.id, [])
        n_rows = max(1, (len(ents) + max_per_row - 1) // max_per_row)
        h = max(_BAND_BASELINE, n_rows * (max_entity_h + row_v_gap) + _LABEL_MARGIN)
        heights.append(h)
    return heights


def compute_pathway_canvas(
    figure: Figure,
    layout_params: dict | None = None,
) -> tuple[float, float]:
    """Return the SVG (width, height) needed to contain this pathway figure.

    Takes entity scale, max-per-row, and row-gap into account. Both
    ``layout_pathway`` (for band geometry) and the compositor (for SVG
    viewport sizing) call this so they always agree on the canvas size.

    Width is always the floor (default 800 px); height grows when any band
    needs more than one entity row or when there are many compartments.

    Args:
        figure: The pathway IR Figure.
        layout_params: Optional overlay onto PATHWAY_DEFAULT_PARAMS. Pass
            the same dict you would pass to ``layout_pathway`` so the canvas
            is computed with the same knobs.

    Returns:
        ``(width, height)`` tuple. Both dimensions are at least the
        ``pathway_canvas`` floor from PATHWAY_DEFAULT_PARAMS.
    """
    params = {**PATHWAY_DEFAULT_PARAMS, **(layout_params or {})}
    min_w, min_h = params["pathway_canvas"]

    if not figure.entities:
        return (float(min_w), float(min_h))

    max_per_row = int(params["pathway_max_per_row"])
    row_v_gap   = float(params["pathway_row_v_gap"])
    scale       = float(params["pathway_entity_scale"])

    _, raw_max_h = max_entity_bbox(figure)
    max_entity_h = raw_max_h * scale

    compartments, location_map = _resolve_compartments(figure)
    by_band: dict[str, list] = {}
    for e in figure.entities:
        by_band.setdefault(location_map[e.id], []).append(e)

    heights = _compute_band_heights(
        compartments, by_band,
        max_per_row=max_per_row,
        row_v_gap=row_v_gap,
        max_entity_h=max_entity_h,
    )
    return (float(min_w), max(len(heights) * _BAND_BASELINE, sum(heights)))


# ---------------------------------------------------------------------------
# V2 / L4: per-arrow annotation glyph helpers
# (defined before RELATION_TO_ARROW so _phosphorylation_arrow is resolvable
#  at module load time)
# ---------------------------------------------------------------------------

# Style fallbacks for the phosphorylation badge.  These keys are present in
# proteins.DEFAULT_STYLE; replicated here so pathway_layout stays independent
# of the proteins module.
_PHOSPHO_BADGE_DEFAULTS: dict = {
    "kinase_badge_fill":       "#D32F2F",
    "kinase_badge_text_color": "#FFFFFF",
    "label_font_size":          11,
    "label_font_family":       "Helvetica, Arial, sans-serif",
    "label_font_color":        "#1A1A1A",
    "protein_stroke":          "#1F4E79",
    "protein_stroke_width":     0.5,
}


def _midpoint_of_path(
    waypoints: list[tuple[float, float]],
) -> tuple[float, float]:
    """Return the geometric midpoint of a polyline (list of ≥ 2 points).

    For a two-point path this is the exact midpoint of the segment. For a
    multi-waypoint elbow path it returns the midpoint of the middle segment
    so the badge sits on the longest visible shaft rather than at a corner.
    """
    if len(waypoints) < 2:
        return waypoints[0]
    if len(waypoints) == 2:
        (x1, y1), (x2, y2) = waypoints
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    mid_i = len(waypoints) // 2
    (x1, y1) = waypoints[mid_i - 1]
    (x2, y2) = waypoints[mid_i]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _relation_glyph(
    group: svgwrite.container.Group,
    cx: float,
    cy: float,
    text: str,
    style: dict,
) -> None:
    """Append a small circular badge carrying ``text`` to ``group`` at (cx, cy).

    The badge uses ``kinase_badge_fill`` / ``kinase_badge_text_color`` style
    keys so it picks up preset overrides automatically. Badge radius scales
    with ``label_font_size`` so it stays proportional across presets.
    """
    font_size = float(style.get("label_font_size", 11))
    r = max(7.0, font_size * 0.75)
    badge = svgwrite.shapes.Circle(
        center=(cx, cy), r=r,
        fill=style.get("kinase_badge_fill", "#D32F2F"),
        stroke=style.get("protein_stroke", "#1F4E79"),
    )
    badge["stroke-width"] = float(style.get("protein_stroke_width", 0.5))
    group.add(badge)
    group.add(_centered_label(
        text, cx, cy, style,
        weight="bold",
        color=style.get("kinase_badge_text_color", "#FFFFFF"),
        size_override=font_size * 0.9,
    ))


def _phosphorylation_arrow(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    style_dict: dict | None = None,
    waypoints: list[tuple[float, float]] | None = None,
) -> svgwrite.container.Group:
    """Activation arrow annotated with a 'P' badge at the shaft midpoint.

    V2 / L4. Calls ``arrows.activation_arrow`` for the shaft/head, then
    overlays a phosphorylation badge so the PHOSPHORYLATES relation type is
    visually distinct from a plain ACTIVATES arrow.
    """
    g = arrows.activation_arrow(start, end, style_dict=style_dict, waypoints=waypoints)
    s = {**_PHOSPHO_BADGE_DEFAULTS, **(style_dict or {})}
    pts = waypoints if waypoints else [start, end]
    cx, cy = _midpoint_of_path(pts)
    _relation_glyph(g, cx, cy, "P", s)
    return g


# ---------------------------------------------------------------------------
# Dispatch tables (public so tests + future archetypes can introspect them).
# ---------------------------------------------------------------------------

RELATION_TO_ARROW: dict[RelationType, Callable[..., svgwrite.container.Group]] = {
    RelationType.ACTIVATES:      arrows.activation_arrow,
    RelationType.INHIBITS:       arrows.inhibition_arrow,
    RelationType.BINDS:          arrows.binding_arrow,
    RelationType.TRANSLOCATES:   arrows.translocation_arrow,
    RelationType.PHOSPHORYLATES: _phosphorylation_arrow,  # V2/L4: annotated with 'P' badge
    RelationType.TRANSCRIBES:    arrows.activation_arrow,
    RelationType.GENERIC:        arrows.activation_arrow,
}


_IMPLICIT_COMPARTMENT_ID = "__implicit__"


# Archetypes that share the "entity-graph laid out across compartment bands"
# shape. All of these route to layout_pathway; the panel engine relies on
# this for sub-archetype dispatch, and standalone callers can pass any of
# them too. REACTION_SCHEME stays out: it has a dedicated engine and a
# different kwargs contract (smiles_map).
_PATHWAY_COMPATIBLE_ARCHETYPES = {
    Archetype.PATHWAY,
    Archetype.WORKFLOW,
    Archetype.CELLULAR_SCHEMATIC,
    Archetype.MECHANISM_CARTOON,
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_compartments(
    figure: Figure,
) -> tuple[list[Compartment], dict[str, str]]:
    """Return (ordered_compartments, entity_id → band_id).

    If `figure.compartments` is empty, synthesizes one implicit band so
    every entity has a band. When compartments are declared but an entity
    has `location is None`, the entity is assigned to the first declared
    compartment (deterministic fallback documented in the module
    docstring).
    """
    if not figure.compartments:
        implicit = Compartment(
            id=_IMPLICIT_COMPARTMENT_ID,
            type=CompartmentType.CUSTOM,
            label="",
        )
        return [implicit], {e.id: implicit.id for e in figure.entities}

    compartments = list(figure.compartments)
    fallback = compartments[0].id
    location_map = {e.id: (e.location or fallback) for e in figure.entities}
    return compartments, location_map


def _compute_bands(
    compartments: list[Compartment],
    canvas: tuple[float, float],
    origin: tuple[float, float],
    *,
    band_heights: list[float] | None = None,
) -> dict[str, tuple[float, float]]:
    """Return compartment id → (band_top_y, band_bottom_y).

    When ``band_heights`` is provided (V2/L3 dynamic mode), each band gets
    exactly the height specified (in compartment declaration order). The
    canvas height is ignored in this mode — the caller is responsible for
    setting it to ``sum(band_heights)`` before passing it on.

    When ``band_heights`` is None (v1 fallback / user-supplied canvas), bands
    evenly partition the canvas height in declaration order.
    """
    _, oy = origin
    if band_heights is None:
        _, h = canvas
        bh = h / len(compartments)
        heights: list[float] = [bh] * len(compartments)
    else:
        heights = band_heights

    result: dict[str, tuple[float, float]] = {}
    y = oy
    for c, h in zip(compartments, heights):
        result[c.id] = (y, y + h)
        y += h
    return result


def _graph_positions(
    figure: Figure,
    bands: dict[str, tuple[float, float]],
    location_map: dict[str, str],
    canvas: tuple[float, float],
    origin: tuple[float, float],
    padding: float,
    seed: int,
    max_per_row: int = 6,
    row_v_gap: float = 16.0,
    entity_sizes: dict | None = None,
    edge_margin: float = 8.0,
) -> dict[str, tuple[float, float]]:
    """Compute (x, y) for every entity.

    y is the vertical center of the entity's compartment band (snap-to-band
    enforces compartment containment). x is derived from a seeded
    `nx.spring_layout` to give the relation graph a say in horizontal
    ordering, then evenly spaced inside the band's horizontal extent so
    primitives don't overlap.

    Band wrap (v2): when a band holds more than `max_per_row` entities,
    rows are stacked vertically around the band's center line with
    `row_v_gap` px of vertical breathing room between row centers.
    Backwards-compatible for small bands: `n <= max_per_row` produces a
    single row at the band center, byte-identical to the v1 placement.
    """
    G = nx.Graph()
    DG = nx.DiGraph()
    for e in figure.entities:
        G.add_node(e.id)
        DG.add_node(e.id)
    for r in figure.relations:
        G.add_edge(r.source, r.target)
        DG.add_edge(r.source, r.target)

    # For DAGs, seed spring_layout with topological-rank x positions so
    # left-to-right order reflects the actual flow direction (A→B→C instead
    # of a U-shape). Falls back to unconstrained spring when cycles exist.
    init_pos: dict | None = None
    if G.number_of_edges() and nx.is_directed_acyclic_graph(DG):
        generations = list(nx.topological_generations(DG))
        max_rank = max(len(generations) - 1, 1)
        init_pos = {}
        for rank, gen in enumerate(generations):
            for node in gen:
                init_pos[node] = (rank / max_rank, 0.0)

    # spring_layout is only meaningful when there are edges to relax; with no
    # relations the result is rotationally symmetric noise that gets discarded
    # by the even-spacing pass below. Skip it for an isolated-entity figure.
    raw = (
        nx.spring_layout(G, seed=seed, pos=init_pos)
        if G.number_of_edges()
        else {}
    )

    w, _ = canvas
    ox, _ = origin
    inner_w = max(w - 2 * padding, 1.0)
    # Row height for vertical stacking. Use the max entity height in the
    # figure so kinase (32) and receptor (60) entities don't clip rows
    # narrower than themselves. When entity_sizes is provided (V2/L9 scaled
    # bboxes), use that table so row height tracks the rendered entity size.
    _sizes = entity_sizes if entity_sizes is not None else ENTITY_BBOX
    row_h = max(_sizes[e.type][1] for e in figure.entities) if figure.entities else 30.0

    by_band: dict[str, list[Entity]] = {}
    for e in figure.entities:
        by_band.setdefault(location_map[e.id], []).append(e)

    pos: dict[str, tuple[float, float]] = {}
    for band_id, ents in by_band.items():
        band_top, band_bottom = bands[band_id]
        center_y = (band_top + band_bottom) / 2
        # spring_layout's x decides ordering inside the band; ties broken
        # by id for determinism.
        sorted_ents = sorted(
            ents,
            key=lambda e: (raw.get(e.id, (0.0, 0.0))[0], e.id),
        )
        n = len(sorted_ents)
        n_rows = max(1, (n + max_per_row - 1) // max_per_row)
        for i, e in enumerate(sorted_ents):
            row = i // max_per_row
            col = i % max_per_row
            # cols_in_row matters only for the final, possibly-partial row.
            cols_in_row = min(max_per_row, n - row * max_per_row)
            if cols_in_row == 1:
                x = ox + w / 2
            else:
                x = ox + padding + inner_w * col / (cols_in_row - 1)
            # Stack rows vertically, centered around the band center.
            y_offset = (row - (n_rows - 1) / 2) * (row_h + row_v_gap)
            # L15: clamp centers so entity bboxes stay inside the canvas.
            ew, eh = _sizes.get(e.type, (30.0, 30.0))
            x = max(ox + edge_margin + ew / 2, min(x, ox + w - edge_margin - ew / 2))
            raw_y = center_y + y_offset
            y = max(
                band_top + edge_margin + eh / 2,
                min(raw_y, band_bottom - edge_margin - eh / 2),
            )
            pos[e.id] = (x, y)
    return pos


def _bbox_exit_point(
    center: tuple[float, float],
    half_w: float,
    half_h: float,
    target: tuple[float, float],
    gap: float = 0.0,
) -> tuple[float, float]:
    """Where the line `center → target` exits an axis-aligned bbox.

    Returns `center` itself if the two points coincide. The optional `gap`
    pushes the exit point another `gap` px along the direction (so an
    arrow's head visually clears the shape). The gap is clamped to the
    line's actual length to avoid overshooting past `target`.
    """
    cx, cy = center
    tx, ty = target
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return center
    inv_x = half_w / abs(dx) if dx else float("inf")
    inv_y = half_h / abs(dy) if dy else float("inf")
    t_edge = min(inv_x, inv_y)
    length = (dx * dx + dy * dy) ** 0.5
    t_gap = gap / length if length else 0.0
    t = min(t_edge + t_gap, 1.0)
    return (cx + t * dx, cy + t * dy)


def _arrow_endpoints(
    src_center: tuple[float, float],
    src_bbox: tuple[float, float],
    tgt_center: tuple[float, float],
    tgt_bbox: tuple[float, float],
    gap: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Inset both ends of a relation arrow to their entity bbox edges + gap."""
    src_w, src_h = src_bbox
    tgt_w, tgt_h = tgt_bbox
    start = _bbox_exit_point(src_center, src_w / 2, src_h / 2, tgt_center, gap)
    end = _bbox_exit_point(tgt_center, tgt_w / 2, tgt_h / 2, src_center, gap)
    return start, end


def _segment_hits_rect(
    p0: tuple[float, float],
    p1: tuple[float, float],
    cx: float,
    cy: float,
    hw: float,
    hh: float,
) -> bool:
    """True if segment p0→p1 intersects the axis-aligned rect centred at
    (cx, cy) with half-extents (hw, hh). Liang–Barsky slab clipping."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    left, right = cx - hw, cx + hw
    bottom, top = cy - hh, cy + hh
    t_enter, t_exit = 0.0, 1.0
    for p, q in (
        (-dx, x0 - left),    # left slab
        (dx, right - x0),    # right slab
        (-dy, y0 - bottom),  # bottom slab
        (dy, top - y0),      # top slab
    ):
        if p == 0:
            # Segment parallel to this slab: outside if origin is outside.
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > t_exit:
                return False
            if t > t_enter:
                t_enter = t
        else:
            if t < t_enter:
                return False
            if t < t_exit:
                t_exit = t
    return t_enter <= t_exit


def _arch_waypoints(
    src_center: tuple[float, float],
    src_bbox: tuple[float, float],
    tgt_center: tuple[float, float],
    tgt_bbox: tuple[float, float],
    band: tuple[float, float],
    gap: float,
    lane: int,
    *,
    above: bool,
    clearance: float,
    lane_gap: float,
) -> list[tuple[float, float]]:
    """4-point elbow that arches a same-band skip arrow over (or under) the
    intervening entities. `lane` (0-based) stacks successive arches into
    distinct corridors so overlapping arches never share a shaft line. The
    corridor is clamped to stay inside the band interior."""
    sx, sy = src_center
    tx, ty = tgt_center
    shh = src_bbox[1] / 2
    thh = tgt_bbox[1] / 2
    band_top, band_bottom = band
    if above:
        base = min(sy - shh, ty - thh) - clearance
        corridor_y = base - lane * lane_gap
        corridor_y = max(corridor_y, band_top + clearance)
        tail = (sx, sy - shh - gap)
        head = (tx, ty - thh - gap)
    else:
        base = max(sy + shh, ty + thh) + clearance
        corridor_y = base + lane * lane_gap
        corridor_y = min(corridor_y, band_bottom - clearance)
        tail = (sx, sy + shh + gap)
        head = (tx, ty + thh + gap)
    return [tail, (sx, corridor_y), (tx, corridor_y), head]


def _route_same_band_arrows(
    relations: list,
    positions: dict[str, tuple[float, float]],
    entity_by_id: dict,
    bands: dict[str, tuple[float, float]],
    location_map: dict[str, str],
    effective_bbox: dict,
    gap: float,
    clearance: float,
    lane_gap: float,
) -> dict[int, list[tuple[float, float]] | None]:
    """Decide waypoints for every same-band relation.

    Returns a map from `relations` index → waypoint list, or ``None`` for a
    straight arrow. An arrow arches when its straight shaft would cross an
    intervening entity in the same band; arches are assigned to lanes via a
    left-edge sweep so overlapping spans never collapse onto one corridor,
    alternating above/below the row to use both sides of the band.
    """
    # Entities grouped per band, for the intervening-entity test.
    band_members: dict[str, list[str]] = {}
    for eid in positions:
        band_members.setdefault(location_map[eid], []).append(eid)

    routes: dict[int, list[tuple[float, float]] | None] = {}
    arching: list[tuple[float, float, int]] = []  # (x_left, x_right, rel_index)

    for idx, r in enumerate(relations):
        if location_map[r.source] != location_map[r.target]:
            continue  # cross-band handled elsewhere
        src = entity_by_id[r.source]
        tgt = entity_by_id[r.target]
        s_center = positions[r.source]
        t_center = positions[r.target]
        s_bbox = effective_bbox[src.type]
        t_bbox = effective_bbox[tgt.type]
        start, end = _arrow_endpoints(s_center, s_bbox, t_center, t_bbox, gap)

        hit = False
        for oid in band_members[location_map[r.source]]:
            if oid in (r.source, r.target):
                continue
            ocx, ocy = positions[oid]
            ow, oh = effective_bbox[entity_by_id[oid].type]
            if _segment_hits_rect(start, end, ocx, ocy, ow / 2, oh / 2):
                hit = True
                break

        if not hit:
            routes[idx] = None  # straight
        else:
            arching.append((min(s_center[0], t_center[0]),
                            max(s_center[0], t_center[0]), idx))

    # Left-edge lane assignment: sort by left x, place each span in the
    # lowest lane whose last span ends before this one starts.
    arching.sort(key=lambda s: (s[0], s[1]))
    lane_right_edge: list[float] = []  # rightmost x occupied per lane
    lane_of: dict[int, int] = {}
    for x_left, x_right, idx in arching:
        placed = False
        for lane, redge in enumerate(lane_right_edge):
            if x_left >= redge:
                lane_right_edge[lane] = x_right
                lane_of[idx] = lane
                placed = True
                break
        if not placed:
            lane_of[idx] = len(lane_right_edge)
            lane_right_edge.append(x_right)

    for x_left, x_right, idx in arching:
        r = relations[idx]
        src = entity_by_id[r.source]
        tgt = entity_by_id[r.target]
        lane = lane_of[idx]
        # Alternate sides: even lanes arch above, odd lanes arch below, so a
        # band uses both halves and fits roughly twice as many arches.
        side_lane = lane // 2
        above = (lane % 2 == 0)
        routes[idx] = _arch_waypoints(
            positions[r.source], effective_bbox[src.type],
            positions[r.target], effective_bbox[tgt.type],
            bands[location_map[r.source]],
            gap, side_lane,
            above=above, clearance=clearance, lane_gap=lane_gap,
        )
    return routes


def _orthogonal_waypoints(
    src_center: tuple[float, float],
    src_bbox: tuple[float, float],
    src_band: tuple[float, float],
    tgt_center: tuple[float, float],
    tgt_bbox: tuple[float, float],
    tgt_band: tuple[float, float],
    gap: float,
) -> list[tuple[float, float]]:
    """Compute a 4-point orthogonal (elbow) path from src to tgt.

    For entities in different bands the path travels through the clear
    corridor between the two bands (no entities occupy that space), so
    it is guaranteed not to pass through any third entity box.

    For entities in the same band the path routes through a corridor
    above the band top (outside the band), which may briefly exit the
    canvas for the top-most band but is still rendered correctly by SVG.

    Returns a 4-element list: [tail_exit, elbow_src, elbow_tgt, head_enter].
    The first and last points land on the bbox perimeters of source and
    target respectively; the middle two define the horizontal corridor leg.
    """
    sx, sy = src_center
    tx, ty = tgt_center
    shw, shh = src_bbox[0] / 2, src_bbox[1] / 2
    thw, thh = tgt_bbox[0] / 2, tgt_bbox[1] / 2
    src_top, src_bottom = src_band
    tgt_top, tgt_bottom = tgt_band

    if src_band == tgt_band:
        # Route above both entity tops within the band, not above the band boundary.
        # This keeps the corridor inside the canvas even when the band spans the
        # full height (single implicit band for figures with no compartments).
        clearance = max(gap * 4, 16.0)
        corridor_y = min(sy - shh, ty - thh) - clearance
        tail = (sx, sy - shh - gap)
        head = (tx, ty - thh - gap)
        return [tail, (sx, corridor_y), (tx, corridor_y), head]

    if src_bottom <= tgt_top:
        # src band is above tgt band in the figure (lower y_range in SVG).
        corridor_y = (src_bottom + tgt_top) / 2
        tail = (sx, sy + shh + gap)
        head = (tx, ty - thh - gap)
    else:
        # src band is below tgt band.
        corridor_y = (tgt_bottom + src_top) / 2
        tail = (sx, sy - shh - gap)
        head = (tx, ty + thh + gap)

    return [tail, (sx, corridor_y), (tx, corridor_y), head]


def _compartment_band(
    label: str,
    x: float,
    y: float,
    w: float,
    h: float,
    params: dict,
    *,
    compartment_type: CompartmentType | None = None,
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Background rectangle + top-left label for one compartment band.

    ``params`` is the already-merged layout-params dict from ``layout_pathway``,
    so caller overrides via ``layout_params={"pathway_band_fill": ...}`` reach
    here.

    V2 / L8: when ``compartment_type`` is ``MEMBRANE`` a horizontal lipid-bilayer
    stripe is drawn along the band's top border; when it is ``NUCLEUS`` a
    double-line nuclear-envelope border is drawn instead. Both use the
    membrane primitive's ``DEFAULT_STYLE`` keys merged with ``style_dict`` so
    preset overrides (e.g. ACS monochrome nuclear strokes) flow through.
    """
    g = svgwrite.container.Group()
    # Mark the band group as decorative chrome (not figure content). The crop
    # / whitespace logic excludes data-role="band" subtrees so a full-canvas
    # background band doesn't defeat content-bbox detection. debug=False lets
    # svgwrite emit the non-allowlisted data-* attribute.
    g._parameter.debug = False
    g.attribs["data-role"] = "band"
    rect = svgwrite.shapes.Rect(
        insert=(x, y),
        size=(w, h),
        fill=params["pathway_band_fill"],
        stroke=params["pathway_band_stroke"],
    )
    rect["stroke-width"] = float(params["pathway_band_stroke_width"])
    g.add(rect)
    if label:
        size = float(params["pathway_band_label_size"])
        g.add(svgwrite.text.Text(
            label,
            insert=(x + 8, y + size + 4),
            font_family=params["pathway_band_label_family"],
            font_size=size,
            fill=params["pathway_band_label_color"],
        ))

    # V2 / L8: organelle-specific border decorations
    if compartment_type in (CompartmentType.MEMBRANE, CompartmentType.NUCLEUS):
        from imageGen.primitives import membranes as _mem  # noqa: PLC0415
        ms: dict = {**_mem.DEFAULT_STYLE, **(style_dict or {})}

        if compartment_type is CompartmentType.MEMBRANE:
            _draw_bilayer_border(g, x, y, w, ms)
        else:  # NUCLEUS
            _draw_nuclear_border(g, x, y, w, ms)

    return g


def _draw_bilayer_border(
    group: svgwrite.container.Group,
    x: float, y: float, w: float,
    ms: dict,
) -> None:
    """Draw a horizontal lipid-bilayer stripe at the top edge of a band.

    Renders: a filled tail-region rectangle, two boundary strokes (outer
    and inner leaflet), and evenly-spaced phospholipid head-group circles
    on both leaflets — the standard textbook membrane representation,
    flattened into a horizontal stripe.
    """
    thickness = float(ms["bilayer_thickness"])
    inner_y = y + thickness

    # Hydrophobic tail fill
    group.add(svgwrite.shapes.Rect(
        insert=(x, y), size=(w, thickness),
        fill=str(ms["bilayer_tail_fill"]), stroke="none",
    ))
    # Outer leaflet boundary stroke
    outer = svgwrite.path.Path(
        d=f"M {x:.2f},{y:.2f} L {x + w:.2f},{y:.2f}",
        fill="none", stroke=str(ms["bilayer_outer_stroke"]),
    )
    outer["stroke-width"] = float(ms["bilayer_outer_stroke_width"])
    group.add(outer)
    # Inner leaflet boundary stroke
    inner = svgwrite.path.Path(
        d=f"M {x:.2f},{inner_y:.2f} L {x + w:.2f},{inner_y:.2f}",
        fill="none", stroke=str(ms["bilayer_inner_stroke"]),
    )
    inner["stroke-width"] = float(ms["bilayer_inner_stroke_width"])
    group.add(inner)
    # Head-group circles on both leaflets
    spacing = float(ms["bilayer_head_spacing"])
    r_head  = float(ms["bilayer_head_radius"])
    fill    = str(ms["bilayer_head_fill"])
    hx = x + spacing
    while hx < x + w - spacing * 0.5:
        group.add(svgwrite.shapes.Circle(center=(hx, y),       r=r_head, fill=fill))
        group.add(svgwrite.shapes.Circle(center=(hx, inner_y), r=r_head, fill=fill))
        hx += spacing


def _draw_nuclear_border(
    group: svgwrite.container.Group,
    x: float, y: float, w: float,
    ms: dict,
) -> None:
    """Draw a horizontal double-line nuclear-envelope border at the top of a band.

    Renders: outer nuclear-membrane stroke, inner nuclear-membrane stroke
    (separated by ``nuclear_gap`` px), and evenly-spaced nuclear-pore-complex
    accent circles between the two lines.
    """
    gap    = float(ms["nuclear_gap"])
    inner_y = y + gap
    pore_r = float(ms["nuclear_pore_radius"])
    pore_n = int(ms["nuclear_pore_count"])

    # Outer nuclear membrane
    outer = svgwrite.path.Path(
        d=f"M {x:.2f},{y:.2f} L {x + w:.2f},{y:.2f}",
        fill="none", stroke=str(ms["nuclear_outer_stroke"]),
    )
    outer["stroke-width"] = float(ms["nuclear_outer_stroke_width"])
    group.add(outer)
    # Inner nuclear membrane
    inner = svgwrite.path.Path(
        d=f"M {x:.2f},{inner_y:.2f} L {x + w:.2f},{inner_y:.2f}",
        fill="none", stroke=str(ms["nuclear_inner_stroke"]),
    )
    inner["stroke-width"] = float(ms["nuclear_inner_stroke_width"])
    group.add(inner)
    # Nuclear pore complex accents at midline between the two strokes
    if pore_n > 0:
        pore_y = y + gap / 2
        spacing = w / (pore_n + 1)
        for i in range(1, pore_n + 1):
            group.add(svgwrite.shapes.Circle(
                center=(x + i * spacing, pore_y),
                r=pore_r,
                fill=str(ms["nuclear_pore_fill"]),
            ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def layout_pathway(
    figure: Figure,
    layout_params: dict | None = None,
    style_dict: dict | None = None,
) -> list[LayoutEntry]:
    """Lay out an IR PATHWAY Figure as a list of LayoutEntry tuples.

    Args:
        figure: IR Figure with archetype=PATHWAY, non-empty entities.
            Compartments are optional (single implicit band synthesized
            when omitted). Relations are optional (isolated-entity
            pathways still produce a layout).
        layout_params: Optional overlay onto PATHWAY_DEFAULT_PARAMS.
            Notable keys: `pathway_canvas`, `pathway_seed`.
        style_dict: Optional preset overlay forwarded to every primitive
            and to `_compartment_band`.

    Returns:
        A list of LayoutEntry tuples in render order: compartment bands
        (background) → entities → relation arrows.

    Raises:
        ValueError: figure.archetype is not PATHWAY, or entities is empty.
    """
    if figure.archetype not in _PATHWAY_COMPATIBLE_ARCHETYPES:
        raise ValueError(
            f"layout_pathway requires archetype in "
            f"{sorted(a.value for a in _PATHWAY_COMPATIBLE_ARCHETYPES)}, "
            f"got {figure.archetype!r}"
        )
    if not figure.entities:
        raise ValueError("layout_pathway requires a non-empty entities list")

    params = {**PATHWAY_DEFAULT_PARAMS, **(layout_params or {})}
    canvas = params["pathway_canvas"]
    origin = params["pathway_origin"]

    # V2 / L9: build effective per-type bboxes by applying pathway_entity_scale
    # to every ENTITY_BBOX entry. Used for arrow routing, row-height calculation,
    # and the explicit `size=` kwarg forwarded to entity primitives. At the
    # default scale of 1.0 this is byte-identical to the V1 output.
    scale = float(params["pathway_entity_scale"])
    effective_bbox: dict = {
        t: (w * scale, h * scale)
        for t, (w, h) in ENTITY_BBOX.items()
    }

    compartments, location_map = _resolve_compartments(figure)

    # V2 / L3: compute per-band heights dynamically unless the caller
    # explicitly supplied a pathway_canvas override (honour their envelope).
    _user_set_canvas = "pathway_canvas" in (layout_params or {})
    if _user_set_canvas:
        per_band_heights = None  # fall back to equal-split of supplied canvas
    else:
        by_band_for_heights: dict[str, list] = {}
        for e in figure.entities:
            by_band_for_heights.setdefault(location_map[e.id], []).append(e)
        max_entity_h = max(effective_bbox[e.type][1] for e in figure.entities)
        per_band_heights = _compute_band_heights(
            compartments, by_band_for_heights,
            max_per_row=int(params["pathway_max_per_row"]),
            row_v_gap=float(params["pathway_row_v_gap"]),
            max_entity_h=max_entity_h,
        )
        total_h = max(canvas[1], sum(per_band_heights))
        canvas = (canvas[0], total_h)

    bands = _compute_bands(compartments, canvas, origin, band_heights=per_band_heights)
    positions = _graph_positions(
        figure, bands, location_map, canvas, origin,
        padding=float(params["pathway_band_padding"]),
        seed=int(params["pathway_seed"]),
        max_per_row=int(params["pathway_max_per_row"]),
        row_v_gap=float(params["pathway_row_v_gap"]),
        entity_sizes=effective_bbox,
        edge_margin=float(params["pathway_edge_margin"]),
    )

    style_kwargs: dict = {"style_dict": style_dict} if style_dict is not None else {}
    cw, _ = canvas
    ox, _ = origin
    arrow_gap = float(params["pathway_arrow_gap"])
    entity_by_id = {e.id: e for e in figure.entities}

    def _entry(
        primitive: Callable, args: tuple, kwargs: dict, ir_id: str | None = None
    ) -> LayoutEntry:
        return LayoutEntry(primitive, args, kwargs, position=(0.0, 0.0), ir_id=ir_id)

    entries: list[LayoutEntry] = []

    # Bands take the full merged params so band-visual overrides via
    # layout_params land here; entity/arrow primitives take only style_dict.
    # V2/L8: pass compartment_type + style_dict for organelle border decorations.
    for c in compartments:
        top, bottom = bands[c.id]
        band_kwargs: dict = {
            "params": params,
            "compartment_type": c.type,
        }
        if style_dict is not None:
            band_kwargs["style_dict"] = style_dict
        entries.append(_entry(
            _compartment_band,
            (c.label, ox, top, cw, bottom - top),
            band_kwargs,
            ir_id=c.id,
        ))

    for e in figure.entities:
        # V2 / L9: forward effective size explicitly so primitives render at
        # the scaled dimensions. Merged after style_kwargs so the size kwarg
        # is always present regardless of whether a style_dict was supplied.
        entity_kwargs = {**style_kwargs, "size": effective_bbox[e.type]}
        entries.append(_entry(
            ENTITY_TO_PRIMITIVE[e.type],
            (e.label, positions[e.id]),
            entity_kwargs,
            ir_id=e.id,
        ))

    # V2 / L1: same-band arrows route straight when clear, or arch over an
    # intervening entity in a distinct lane when not. Cross-band arrows keep
    # the inter-band corridor routing. Same-band routes are decided together
    # so overlapping arches can be assigned separate lanes.
    same_band_routes = _route_same_band_arrows(
        figure.relations, positions, entity_by_id, bands, location_map,
        effective_bbox, arrow_gap,
        clearance=float(params["pathway_arch_clearance"]),
        lane_gap=float(params["pathway_arch_lane_gap"]),
    )

    for idx, r in enumerate(figure.relations):
        src = entity_by_id[r.source]
        tgt = entity_by_id[r.target]
        start, end = _arrow_endpoints(
            positions[r.source], effective_bbox[src.type],
            positions[r.target], effective_bbox[tgt.type],
            arrow_gap,
        )
        if location_map[r.source] != location_map[r.target]:
            wps = _orthogonal_waypoints(
                positions[r.source], effective_bbox[src.type], bands[location_map[r.source]],
                positions[r.target], effective_bbox[tgt.type], bands[location_map[r.target]],
                arrow_gap,
            )
        else:
            wps = same_band_routes.get(idx)  # None → straight arrow
        arrow_kwargs: dict = {**style_kwargs, "waypoints": wps}
        entries.append(_entry(
            RELATION_TO_ARROW[r.type],
            (start, end),
            arrow_kwargs,
            ir_id=r.ir_id,
        ))

    return entries


def pathway_label_requests(
    figure: Figure,
    entries: list[LayoutEntry],
    layout_params: dict | None = None,
) -> list:
    """Emit one `LabelRequest` per labeled relation in a pathway figure.

    Walks `figure.relations`; for each relation whose `label` is a
    non-empty string, anchors a request at the midpoint of the
    corresponding arrow's start/end (read back from the matching arrow
    LayoutEntry). The anchor bbox is small (a thin shaft point), so
    label_placement's offset gap dominates the spacing.

    Imported lazily by `label_placement.py` callers; declared here so
    the IR-shape walk lives next to its archetype's other concerns.
    Returns `list[label_placement.LabelRequest]` (typed as `list` to
    avoid an import cycle in this module).

    Args:
        figure: The same IR Figure passed to `layout_pathway`.
        entries: The exact list returned from `layout_pathway(figure)`.
            Used to recover the bbox-inset arrow endpoints (so labels
            anchor at the rendered arrow midpoint, not the raw entity
            centers).
        layout_params: Optional overlay; reserved for future use
            (currently no params are read).

    Returns:
        A list of LabelRequest items, one per `Relation.label` that is
        truthy. Empty when no relations carry labels.
    """
    from imageGen.layout.label_placement import LabelRequest  # noqa: PLC0415 — break import cycle

    arrow_entries = [e for e in entries if e.primitive in RELATION_TO_ARROW.values()]
    if len(arrow_entries) != len(figure.relations):
        raise ValueError(
            "pathway_label_requests requires the entries list returned by "
            "layout_pathway(figure); arrow count does not match relations"
        )
    requests: list[LabelRequest] = []
    for relation, arrow in zip(figure.relations, arrow_entries):
        text = relation.label
        if not text:
            continue
        (sx, sy), (ex, ey) = arrow.args
        midpoint = ((sx + ex) / 2, (sy + ey) / 2)
        # Place the label perpendicular to the arrow shaft so it doesn't
        # render directly on top of the line. For a mostly-horizontal arrow
        # try above/below first; for a mostly-vertical arrow try right/left
        # first. The default priority ("right", "below", ...) would put a
        # horizontal-arrow label at the same y as the arrow itself.
        dx, dy = ex - sx, ey - sy
        if abs(dx) >= abs(dy):
            priority = ("above", "below", "right", "left", "center")
        else:
            priority = ("right", "left", "above", "below", "center")
        # Anchor is a notional point on the arrow shaft; small bbox so
        # label_placement's gap dominates spacing.
        requests.append(LabelRequest(
            text=text,
            anchor=midpoint,
            anchor_size=(2.0, 2.0),
            priority=priority,
            ir_id=relation.ir_id,
        ))
    return requests
