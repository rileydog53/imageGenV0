"""Bug 3 regression: receptor entity label must be visible to layout.

The receptor primitive renders its label to the LEFT of the body (text-anchor:end,
6 px gap from the body left edge).  Previously, both the collision engine and the
arrow-routing engine used only the 28×60 body bbox, so binding arrows passed
straight through the label text.  This file pins the corrected behaviour:

  1. _entry_bbox() for a receptor LayoutEntry extends leftward beyond the body,
     covering the label text area.
  2. _arrow_bbox_for_entity() inflates the effective width for receptor entities.
  3. _arrow_endpoints() routes the endpoint past the label when source is a receptor.
"""
from __future__ import annotations

import pytest

from imageGen.layout._geom import ENTITY_BBOX
from imageGen.ir.schema import EntityType
from imageGen.layout.label_placement import _entry_bbox
from imageGen.layout.pathway_layout import _arrow_bbox_for_entity, _arrow_endpoints
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
