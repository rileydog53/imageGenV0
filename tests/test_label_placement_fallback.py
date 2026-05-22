"""Tests for the v2 relax-and-retry label-placement fallback ladder.

Covers each rung of `_place_with_fallback` (full → shrink → nudge → overlap),
the `data-overlap="true"` SVG marker, and that `legibility_check` tolerates a
deliberately-overlapping flagged label. Geometry is exercised through direct
`_place_with_fallback` calls with hand-built `occupied` boxes so the
collision math is precise and not coupled to entity-primitive sizing.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import svgwrite

from imageGen.layout.label_placement import (
    _FONT_SHRINK_FACTOR,
    LabelRequest,
    _label_primitive,
    _place_with_fallback,
    place_labels,
)
from imageGen.layout.types import LayoutEntry
from imageGen.primitives import proteins
from imageGen.verify.legibility_check import LegibilityCheckError, legibility_check

_GAP = 4.0
_MARGIN = 1.0
_FONT = 11.0


# ---------------------------------------------------------------------------
# Ladder rungs
# ---------------------------------------------------------------------------


def test_pass1_full_size_when_clear():
    """No obstruction → label lands at full font, no overlap flag."""
    req = LabelRequest(text="AAAA", anchor=(100, 100), anchor_size=(2, 2),
                       priority=("right",))
    _center, _bbox, font_used, overlap = _place_with_fallback(
        req, [], _GAP, _MARGIN, _FONT
    )
    assert font_used == _FONT
    assert overlap is False


def test_pass2_shrinks_font_when_full_blocked():
    """A blocker that clips the full-size slot but clears the shrunk slot
    forces a one-step font shrink (Pass 2)."""
    req = LabelRequest(text="AAAA", anchor=(100, 100), anchor_size=(2, 2),
                       priority=("right",))
    # Full 'right' bbox reaches x≈131.4; shrunk reaches x≈127.4. A blocker at
    # x≥130 collides with full but not shrunk.
    occupied = [(130.0, 90.0, 200.0, 110.0)]
    _center, _bbox, font_used, overlap = _place_with_fallback(
        req, occupied, _GAP, _MARGIN, _FONT
    )
    assert overlap is False
    assert font_used == pytest.approx(_FONT * _FONT_SHRINK_FACTOR)


def test_pass3_nudges_anchor_when_shrink_blocked():
    """A blocker covering both the full and shrunk in-place slot, but leaving
    a sliver clear 8px to one side, is escaped by an anchor nudge (Pass 3)."""
    req = LabelRequest(text="X", anchor=(100, 100), anchor_size=(2, 2),
                       priority=("right",))
    # Shrunk in-place 'right' bbox spans x≈[105,110.6]; this blocker overlaps
    # it, but a -8px x-nudge slides the label left to x≈[97,102.6], clearing.
    occupied = [(109.0, 94.0, 130.0, 106.0)]
    center, _bbox, font_used, overlap = _place_with_fallback(
        req, occupied, _GAP, _MARGIN, _FONT
    )
    assert overlap is False
    assert font_used == pytest.approx(_FONT * _FONT_SHRINK_FACTOR)
    # The rescuing nudge was to the left of the in-place 'right' slot.
    assert center[0] < 107.0


def test_pass4_last_resort_overlap_when_boxed_in():
    """Everything around the anchor is occupied → last-resort placement with
    the overlap flag set (Pass 4)."""
    req = LabelRequest(text="boxed", anchor=(300, 300), anchor_size=(2, 2))
    occupied = [(0.0, 0.0, 600.0, 600.0)]  # the whole region is blocked
    _center, _bbox, font_used, overlap = _place_with_fallback(
        req, occupied, _GAP, _MARGIN, _FONT
    )
    assert overlap is True
    assert font_used == _FONT  # last resort renders at full size


# ---------------------------------------------------------------------------
# place_labels integration — overlap flag + warning
# ---------------------------------------------------------------------------


def test_place_labels_emits_overlap_kwarg_and_warns():
    """A boxed-in request placed leniently carries overlap=True and warns."""
    blocker = LayoutEntry(
        primitive=proteins.generic_protein,
        args=("Blk", (300, 300)),
        kwargs={},
        position=(0.0, 0.0),
    )
    req = LabelRequest(text="boxed", anchor=(300, 300), anchor_size=(2, 2))
    with pytest.warns(UserWarning, match="overlap"):
        out = place_labels([blocker], [req])
    label = next(e for e in out if e.primitive is _label_primitive)
    assert label.kwargs.get("overlap") is True


# ---------------------------------------------------------------------------
# data-overlap SVG marker + legibility tolerance
# ---------------------------------------------------------------------------


def _strip(tag: str) -> str:
    return tag.split("}")[-1]


def test_label_primitive_emits_data_overlap_attribute():
    """_label_primitive(overlap=True) tags the rendered <text> with data-overlap."""
    group = _label_primitive("hi", (50.0, 50.0), overlap=True)
    dwg = svgwrite.Drawing(size=(100, 100), debug=False)
    dwg.add(group)
    xml = dwg.tostring()
    root = ET.fromstring(xml)
    texts = [el for el in root.iter() if _strip(el.tag) == "text"]
    assert texts and texts[0].get("data-overlap") == "true"


def test_label_primitive_no_marker_by_default():
    """Without overlap=True, no data-overlap attribute is emitted."""
    group = _label_primitive("hi", (50.0, 50.0))
    dwg = svgwrite.Drawing(size=(100, 100), debug=False)
    dwg.add(group)
    root = ET.fromstring(dwg.tostring())
    texts = [el for el in root.iter() if _strip(el.tag) == "text"]
    assert texts and texts[0].get("data-overlap") is None


def _write_two_label_svg(path: Path, *, flag_second: bool) -> None:
    """Write a minimal SVG with two overlapping <text> labels."""
    dwg = svgwrite.Drawing(str(path), size=(200, 200), debug=False)
    dwg.add(_label_primitive("alpha", (100.0, 100.0)))
    dwg.add(_label_primitive("alpha", (104.0, 102.0), overlap=flag_second))
    dwg.save()


def test_legibility_raises_on_unflagged_overlap(tmp_path):
    """Two genuinely-overlapping unflagged labels still raise."""
    svg = tmp_path / "unflagged.svg"
    _write_two_label_svg(svg, flag_second=False)
    with pytest.raises(LegibilityCheckError):
        legibility_check(svg)


def test_legibility_tolerates_flagged_overlap(tmp_path):
    """The same overlap is tolerated when one label carries data-overlap."""
    svg = tmp_path / "flagged.svg"
    _write_two_label_svg(svg, flag_second=True)
    result = legibility_check(svg)  # must not raise
    assert result is not None
