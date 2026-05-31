"""Bug 2 regression: relation labels must not be placed on an arrow shaft.

Arrows were zero-footprint to the greedy placement engine, so a label could
land directly on a line. `place_labels` now reserves a thin corridor sampled
along every arrow shaft. This test pins that behaviour.
"""
from __future__ import annotations

from imageGen.layout.label_placement import (
    LabelRequest,
    place_labels,
    _label_primitive,
    _SHAFT_HALF_WIDTH,
)
from imageGen.layout.types import LayoutEntry
from imageGen.primitives import arrows


def _seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _arrow_entry(start, end, waypoints=None):
    kwargs = {"waypoints": waypoints} if waypoints else {}
    return LayoutEntry(
        primitive=arrows.activation_arrow,
        args=(start, end),
        kwargs=kwargs,
        position=(0.0, 0.0),
        ir_id="r1",
    )


def test_label_avoids_horizontal_shaft():
    """A label anchored on a horizontal shaft midpoint is pushed off the line."""
    shaft = _arrow_entry((100.0, 200.0), (300.0, 200.0))
    # Anchor the label right on the shaft midpoint, with a priority that would
    # otherwise centre it on the line.
    req = LabelRequest(
        text="catalyse",
        anchor=(200.0, 200.0),
        anchor_size=(2.0, 2.0),
        priority=("center", "above", "below", "left", "right"),
    )
    placed = place_labels([shaft], [req], canvas=(400.0, 400.0))
    labels = [e for e in placed if e.primitive is _label_primitive]
    assert len(labels) == 1
    center = labels[0].args[1]
    d = _seg_dist(center, (100.0, 200.0), (300.0, 200.0))
    assert d >= _SHAFT_HALF_WIDTH, f"label center sits on the shaft (d={d:.1f})"


def test_label_avoids_elbow_waypoint_shaft():
    """The reserved corridor follows the rendered elbow, not just the chord."""
    wps = [(100.0, 100.0), (100.0, 300.0), (300.0, 300.0)]
    shaft = _arrow_entry(wps[0], wps[-1], waypoints=wps)
    # Anchor on the vertical leg of the elbow.
    req = LabelRequest(
        text="x",
        anchor=(100.0, 200.0),
        anchor_size=(2.0, 2.0),
        priority=("center", "right", "left", "above", "below"),
    )
    placed = place_labels([shaft], [req], canvas=(500.0, 500.0))
    labels = [e for e in placed if e.primitive is _label_primitive]
    center = labels[0].args[1]
    dmin = min(_seg_dist(center, a, b) for a, b in zip(wps, wps[1:]))
    assert dmin >= _SHAFT_HALF_WIDTH, f"label sits on the elbow shaft (d={dmin:.1f})"
