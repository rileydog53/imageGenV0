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
import svgwrite.shapes
import svgwrite.text

from ir.schema import (
    Archetype,
    Compartment,
    CompartmentType,
    Entity,
    EntityType,
    Figure,
    RelationType,
)
from layout.reaction_layout import LayoutEntry
from primitives import arrows, proteins


# ---------------------------------------------------------------------------
# Layout knobs (Phase 4 master preset will union these alongside primitive
# DEFAULT_STYLE dicts; flat namespaced keys for predictable union).
# ---------------------------------------------------------------------------

DEFAULT_LAYOUT_PARAMS: dict[str, Any] = {
    "pathway_canvas":            (800.0, 600.0),    # (w, h) of figure area
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
}


# Per-EntityType bounding boxes (w, h), tracking each primitive's default
# size in `primitives/proteins.py`. Used to inset arrow endpoints to the
# entity's perimeter so shafts/heads never overlap entity labels. Keep in
# sync if a primitive's default size changes; Phase 4's master preset will
# centralise this so the table can come from style instead.
_ENTITY_BBOX: dict[EntityType, tuple[float, float]] = {
    EntityType.PROTEIN:    (60.0, 30.0),
    EntityType.LIGAND:     (60.0, 30.0),
    EntityType.RECEPTOR:   (28.0, 60.0),
    EntityType.KINASE:     (70.0, 32.0),
    EntityType.GENE:       (60.0, 30.0),
    EntityType.METABOLITE: (60.0, 30.0),
    EntityType.CELL:       (60.0, 30.0),
    EntityType.ORGANELLE:  (60.0, 30.0),
    EntityType.EQUIPMENT:  (60.0, 30.0),
    EntityType.SAMPLE:     (60.0, 30.0),
    EntityType.GENERIC:    (60.0, 30.0),
}


# ---------------------------------------------------------------------------
# Dispatch tables (public so tests + future archetypes can introspect them).
# ---------------------------------------------------------------------------

ENTITY_TO_PRIMITIVE: dict[EntityType, Callable[..., svgwrite.container.Group]] = {
    EntityType.PROTEIN:    proteins.generic_protein,
    EntityType.LIGAND:     proteins.generic_protein,
    EntityType.RECEPTOR:   proteins.receptor,
    EntityType.KINASE:     proteins.kinase,
    EntityType.GENE:       proteins.generic_protein,
    EntityType.METABOLITE: proteins.generic_protein,
    EntityType.CELL:       proteins.generic_protein,
    EntityType.ORGANELLE:  proteins.generic_protein,
    EntityType.EQUIPMENT:  proteins.generic_protein,
    EntityType.SAMPLE:     proteins.generic_protein,
    EntityType.GENERIC:    proteins.generic_protein,
}

RELATION_TO_ARROW: dict[RelationType, Callable[..., svgwrite.container.Group]] = {
    RelationType.ACTIVATES:      arrows.activation_arrow,
    RelationType.INHIBITS:       arrows.inhibition_arrow,
    RelationType.BINDS:          arrows.binding_arrow,
    RelationType.TRANSLOCATES:   arrows.translocation_arrow,
    RelationType.PHOSPHORYLATES: arrows.activation_arrow,
    RelationType.TRANSCRIBES:    arrows.activation_arrow,
    RelationType.GENERIC:        arrows.activation_arrow,
}


_IMPLICIT_COMPARTMENT_ID = "__implicit__"


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
) -> dict[str, tuple[float, float]]:
    """Return compartment id → (band_top_y, band_bottom_y).

    Bands evenly partition the canvas vertically in declaration order:
    compartment 0 sits at the top, the last compartment at the bottom.
    """
    _, h = canvas
    _, oy = origin
    band_h = h / len(compartments)
    return {
        c.id: (oy + i * band_h, oy + (i + 1) * band_h)
        for i, c in enumerate(compartments)
    }


def _graph_positions(
    figure: Figure,
    bands: dict[str, tuple[float, float]],
    location_map: dict[str, str],
    canvas: tuple[float, float],
    origin: tuple[float, float],
    padding: float,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """Compute (x, y) for every entity.

    y is the vertical center of the entity's compartment band (snap-to-band
    enforces compartment containment). x is derived from a seeded
    `nx.spring_layout` to give the relation graph a say in horizontal
    ordering, then evenly spaced inside the band's horizontal extent so
    primitives don't overlap.
    """
    G = nx.Graph()
    for e in figure.entities:
        G.add_node(e.id)
    for r in figure.relations:
        G.add_edge(r.source, r.target)

    # spring_layout is only meaningful when there are edges to relax; with no
    # relations the result is rotationally symmetric noise that gets discarded
    # by the even-spacing pass below. Skip it for an isolated-entity figure.
    raw = (
        nx.spring_layout(G, seed=seed)
        if G.number_of_edges()
        else {}
    )

    w, _ = canvas
    ox, _ = origin
    inner_w = max(w - 2 * padding, 1.0)

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
        for i, e in enumerate(sorted_ents):
            x = ox + w / 2 if n == 1 else ox + padding + inner_w * i / (n - 1)
            pos[e.id] = (x, center_y)
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


def _compartment_band(
    label: str,
    x: float,
    y: float,
    w: float,
    h: float,
    params: dict,
) -> svgwrite.container.Group:
    """Background rectangle + top-left label for one compartment band.

    `params` is the already-merged layout-params dict from `layout_pathway`,
    so caller overrides via `layout_params={"pathway_band_fill": ...}` reach
    here. This avoids a second source of truth (a separate style_dict merge
    inside the helper) and keeps band visuals owned by the layout engine.
    """
    g = svgwrite.container.Group()
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
    return g


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
        layout_params: Optional overlay onto DEFAULT_LAYOUT_PARAMS.
            Notable keys: `pathway_canvas`, `pathway_seed`.
        style_dict: Optional preset overlay forwarded to every primitive
            and to `_compartment_band`.

    Returns:
        A list of LayoutEntry tuples in render order: compartment bands
        (background) → entities → relation arrows.

    Raises:
        ValueError: figure.archetype is not PATHWAY, or entities is empty.
    """
    if figure.archetype != Archetype.PATHWAY:
        raise ValueError(
            f"layout_pathway requires archetype=PATHWAY, "
            f"got {figure.archetype!r}"
        )
    if not figure.entities:
        raise ValueError("layout_pathway requires a non-empty entities list")

    params = {**DEFAULT_LAYOUT_PARAMS, **(layout_params or {})}
    canvas = params["pathway_canvas"]
    origin = params["pathway_origin"]

    compartments, location_map = _resolve_compartments(figure)
    bands = _compute_bands(compartments, canvas, origin)
    positions = _graph_positions(
        figure, bands, location_map, canvas, origin,
        padding=float(params["pathway_band_padding"]),
        seed=int(params["pathway_seed"]),
    )

    style_kwargs: dict = {"style_dict": style_dict} if style_dict is not None else {}
    cw, _ = canvas
    ox, _ = origin
    arrow_gap = float(params["pathway_arrow_gap"])
    entity_by_id = {e.id: e for e in figure.entities}

    def _entry(primitive: Callable, args: tuple, kwargs: dict) -> LayoutEntry:
        return LayoutEntry(primitive, args, kwargs, position=(0.0, 0.0))

    entries: list[LayoutEntry] = []

    # Bands take the full merged params so band-visual overrides via
    # layout_params land here; entity/arrow primitives take only style_dict.
    for c in compartments:
        top, bottom = bands[c.id]
        entries.append(_entry(
            _compartment_band,
            (c.label, ox, top, cw, bottom - top),
            {"params": params},
        ))

    for e in figure.entities:
        entries.append(_entry(
            ENTITY_TO_PRIMITIVE[e.type],
            (e.label, positions[e.id]),
            style_kwargs,
        ))

    for r in figure.relations:
        src = entity_by_id[r.source]
        tgt = entity_by_id[r.target]
        start, end = _arrow_endpoints(
            positions[r.source], _ENTITY_BBOX[src.type],
            positions[r.target], _ENTITY_BBOX[tgt.type],
            arrow_gap,
        )
        entries.append(_entry(
            RELATION_TO_ARROW[r.type],
            (start, end),
            style_kwargs,
        ))

    return entries
