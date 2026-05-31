"""Bug 3 regression: receptor entity label must be visible to layout.

The receptor primitive renders its label to the LEFT of the body (text-anchor:end,
6 px gap from the body left edge).  Previously, both the collision engine and the
arrow-routing engine used only the 28×60 body bbox, so binding arrows passed
straight through the label text.  This file pins the corrected behaviour:

  1. _entry_bbox() for a receptor LayoutEntry extends leftward beyond the body,
     covering the label text area.
  2. _arrow_bbox_for_entity() inflates the effective width for receptor entities.
  3. _arrow_endpoints() routes the endpoint past the label when source is a receptor.

Bug 3 canvas-side tail: a receptor placed flush-left had its left-anchored label
clipped at the canvas origin (e.g. "INSR" rendering as "NSR").  _graph_positions
now reserves the label overhang in the left clamp bound, so the leftmost
receptor's label x-extent stays on-canvas (x >= 0).
"""
from __future__ import annotations

import pytest

from imageGen.layout._geom import ENTITY_BBOX
from imageGen.ir.schema import (
    Archetype,
    Compartment,
    CompartmentType,
    Entity,
    EntityType,
    Figure,
    Relation,
    RelationType,
)
from imageGen.layout.label_placement import _entry_bbox
from imageGen.layout.pathway_layout import (
    _arrow_bbox_for_entity,
    _arrow_endpoints,
    _left_label_extent,
    layout_pathway,
)
from imageGen.layout.types import LayoutEntry
from imageGen.primitives import proteins


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _receptor_entry(label: str, cx: float, cy: float) -> LayoutEntry:
    bw, bh = ENTITY_BBOX[EntityType.RECEPTOR]
    return LayoutEntry(
        primitive=proteins.receptor,
        args=(label, (cx, cy)),
        kwargs={"size": (bw, bh)},
        position=(0.0, 0.0),
        ir_id="e_test",
    )


class _FakeEntity:
    def __init__(self, etype: EntityType, label: str) -> None:
        self.type = etype
        self.label = label


# ---------------------------------------------------------------------------
# _entry_bbox tests
# ---------------------------------------------------------------------------

def test_entry_bbox_receptor_extends_left():
    """Receptor collision bbox left edge lies beyond the body left edge."""
    cx, cy = 200.0, 150.0
    bw, bh = ENTITY_BBOX[EntityType.RECEPTOR]   # (28, 60)
    body_left = cx - bw / 2

    bbox = _entry_bbox(_receptor_entry("EGFR", cx, cy))
    assert bbox is not None
    x0, y0, x1, y1 = bbox

    assert x0 < body_left, (
        f"left edge {x0:.1f} must be left of body edge {body_left:.1f}"
    )


def test_entry_bbox_receptor_right_edge_unchanged():
    """Receptor collision bbox right edge stays at the body right edge."""
    cx, cy = 200.0, 150.0
    bw, bh = ENTITY_BBOX[EntityType.RECEPTOR]
    body_right = cx + bw / 2

    bbox = _entry_bbox(_receptor_entry("EGFR", cx, cy))
    assert bbox is not None
    _x0, _y0, x1, _y1 = bbox

    assert x1 == pytest.approx(body_right, abs=1.0)


def test_entry_bbox_receptor_covers_label_text():
    """Left edge reaches at least the estimated label text left boundary."""
    cx, cy = 200.0, 150.0
    label = "EGFR"
    bw, _bh = ENTITY_BBOX[EntityType.RECEPTOR]

    bbox = _entry_bbox(_receptor_entry(label, cx, cy))
    assert bbox is not None
    x0 = bbox[0]

    body_half = bw / 2
    gap = 6.0
    est_text_w = max(1, len(label)) * 11.0 * 0.6
    expected_left = cx - body_half - gap - est_text_w
    assert x0 <= expected_left + 0.5, (
        f"left {x0:.1f} doesn't reach label estimate {expected_left:.1f}"
    )


def test_entry_bbox_non_receptor_symmetric():
    """Non-receptor bbox stays symmetric (existing behaviour unchanged)."""
    cx, cy = 100.0, 100.0
    bw, bh = ENTITY_BBOX[EntityType.PROTEIN]
    entry = LayoutEntry(
        primitive=proteins.generic_protein,
        args=("ERK", (cx, cy)),
        kwargs={"size": (bw, bh)},
        position=(0.0, 0.0),
        ir_id="e_erk",
    )
    bbox = _entry_bbox(entry)
    assert bbox is not None
    x0, _y0, x1, _y1 = bbox
    assert abs(x1 - cx) == pytest.approx(abs(cx - x0), abs=2.0)


# ---------------------------------------------------------------------------
# _arrow_bbox_for_entity tests
# ---------------------------------------------------------------------------

def test_arrow_bbox_receptor_wider_than_body():
    bw, bh = ENTITY_BBOX[EntityType.RECEPTOR]
    entity = _FakeEntity(EntityType.RECEPTOR, "EGFR")
    ew, eh = _arrow_bbox_for_entity(entity, (bw, bh))
    assert ew > bw
    assert eh == bh


def test_arrow_bbox_non_receptor_unchanged():
    bw, bh = ENTITY_BBOX[EntityType.PROTEIN]
    entity = _FakeEntity(EntityType.PROTEIN, "ERK")
    assert _arrow_bbox_for_entity(entity, (bw, bh)) == (bw, bh)


# ---------------------------------------------------------------------------
# End-to-end: arrow endpoint clears the label
# ---------------------------------------------------------------------------

def test_receptor_source_arrow_exits_past_body_left_edge():
    """Arrow start at receptor exits past the body left edge toward target."""
    label = "EGFR"
    bw, bh = ENTITY_BBOX[EntityType.RECEPTOR]
    cx, cy = 200.0, 150.0
    entity = _FakeEntity(EntityType.RECEPTOR, label)
    tgt_center = (100.0, 150.0)   # target is to the LEFT of the receptor

    extended = _arrow_bbox_for_entity(entity, (bw, bh))
    start, _end = _arrow_endpoints(
        (cx, cy), extended,
        tgt_center, ENTITY_BBOX[EntityType.PROTEIN],
        gap=4.0,
    )

    body_left = cx - bw / 2
    assert start[0] < body_left, (
        f"Arrow start x={start[0]:.1f} must be left of body edge {body_left:.1f}"
    )


# ---------------------------------------------------------------------------
# Bug 3 canvas-side tail: leftmost receptor label stays on-canvas
# ---------------------------------------------------------------------------

def _receptor_label_left_x(figure: Figure, receptor_id: str) -> float:
    """Estimated left x of a receptor's left-anchored label after layout.

    The receptor primitive draws its label at ``cx - ec_w/2 - gap`` with
    ``text-anchor="end"``, so the leftmost text pixel is another ``label_w``
    further left.  Mirror that estimate from the laid-out center.
    """
    entries = layout_pathway(figure)
    entity = next(e for e in figure.entities if e.id == receptor_id)
    entry = next(e for e in entries if e.ir_id == receptor_id)
    cx = entry.args[1][0]
    ec_w = ENTITY_BBOX[EntityType.RECEPTOR][0]
    return cx - ec_w / 2 - _left_label_extent(entity)


def test_layered_leftmost_receptor_label_on_canvas():
    """Compartment-free layered DAG: rank-0 receptor label x stays >= 0."""
    figure = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="insr", type=EntityType.RECEPTOR, label="INSR"),
            Entity(id="irs1", type=EntityType.PROTEIN, label="IRS1"),
            Entity(id="akt", type=EntityType.KINASE, label="AKT"),
        ],
        relations=[
            Relation(source="insr", target="irs1", type=RelationType.ACTIVATES),
            Relation(source="irs1", target="akt", type=RelationType.ACTIVATES),
        ],
    )
    label_left = _receptor_label_left_x(figure, "insr")
    assert label_left >= 0.0, f"label left x={label_left:.1f} is clipped (< 0)"


def test_band_snap_leftmost_receptor_label_on_canvas():
    """Membrane-band figure with the receptor pinned to the first column."""
    figure = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="insr", type=EntityType.RECEPTOR, label="INSR", location="m"),
            Entity(id="egfr", type=EntityType.RECEPTOR, label="EGFR", location="m"),
            Entity(id="akt", type=EntityType.KINASE, label="AKT", location="c"),
        ],
        compartments=[
            Compartment(id="m", type=CompartmentType.MEMBRANE, label="Membrane"),
            Compartment(id="c", type=CompartmentType.CYTOPLASM, label="Cytoplasm"),
        ],
        relations=[
            Relation(source="insr", target="akt", type=RelationType.ACTIVATES),
            Relation(source="egfr", target="akt", type=RelationType.ACTIVATES),
        ],
    )
    for rid in ("insr", "egfr"):
        label_left = _receptor_label_left_x(figure, rid)
        assert label_left >= 0.0, (
            f"{rid} label left x={label_left:.1f} is clipped (< 0)"
        )


def test_left_label_extent_zero_for_non_receptor():
    """Only receptors carry a left-side label overhang."""
    protein = _FakeEntity(EntityType.PROTEIN, "ERK")
    receptor = _FakeEntity(EntityType.RECEPTOR, "INSR")
    assert _left_label_extent(protein) == 0.0
    assert _left_label_extent(receptor) > 0.0
