"""Phase 3 Step 4 tests for layout/label_placement.py."""
from __future__ import annotations

import pytest
import svgwrite
import svgwrite.container

from imageGen.ir.schema import Figure
from imageGen.layout.label_placement import (
    DEFAULT_LAYOUT_PARAMS,
    LabelPlacementError,
    LabelRequest,
    _estimate_text_bbox,
    _label_primitive,
    place_labels,
)
from imageGen.layout.pathway_layout import (
    RELATION_TO_ARROW,
    layout_pathway,
    pathway_label_requests,
)
from imageGen.layout.types import LayoutEntry
from imageGen.primitives import proteins
from tests._helpers import load_fixture, render_entries_to_png


def _entity_entry(label: str, position: tuple[float, float]) -> LayoutEntry:
    """Build a synthetic entity LayoutEntry for collision-anchor tests."""
    return LayoutEntry(
        primitive=proteins.generic_protein,
        args=(label, position),
        kwargs={},
        position=(0.0, 0.0),
    )


def _label_entries(entries: list[LayoutEntry]) -> list[LayoutEntry]:
    return [e for e in entries if e.primitive is _label_primitive]


# ---------------------------------------------------------------------------
# DEFAULT_LAYOUT_PARAMS / namespacing
# ---------------------------------------------------------------------------

def test_default_layout_params_completeness():
    for key in ("label_anchor_gap", "label_collision_margin"):
        assert key in DEFAULT_LAYOUT_PARAMS
        assert isinstance(DEFAULT_LAYOUT_PARAMS[key], float)


def test_default_layout_params_keys_are_namespaced():
    for key in DEFAULT_LAYOUT_PARAMS:
        assert key.startswith("label_"), f"non-namespaced key: {key}"


# ---------------------------------------------------------------------------
# LabelRequest validation
# ---------------------------------------------------------------------------

def test_label_request_default_priority():
    req = LabelRequest(text="x", anchor=(0, 0), anchor_size=(2, 2))
    assert req.priority == ("right", "below", "above", "left", "center")


def test_label_request_validates_priority_strings():
    with pytest.raises(ValueError, match="unknown name"):
        LabelRequest(
            text="x", anchor=(0, 0), anchor_size=(2, 2),
            priority=("right", "northeast"),
        )


# ---------------------------------------------------------------------------
# place_labels — basic shape
# ---------------------------------------------------------------------------

def test_place_labels_returns_entries_plus_labels():
    req = LabelRequest(text="hello", anchor=(100, 100), anchor_size=(2, 2))
    out = place_labels(entries=[], label_requests=[req])
    assert len(out) == 1
    assert out[0].primitive is _label_primitive
    text, _ = out[0].args
    assert text == "hello"


def test_place_labels_preserves_input_entries_order():
    e1 = _entity_entry("E1", (50, 50))
    e2 = _entity_entry("E2", (200, 200))
    req = LabelRequest(text="lbl", anchor=(400, 400), anchor_size=(2, 2))
    out = place_labels([e1, e2], [req])
    assert out[:2] == [e1, e2]
    assert out[2].primitive is _label_primitive


def test_place_labels_first_priority_when_no_collision():
    """An anchor in empty space — label lands at first priority ('right')."""
    req = LabelRequest(text="L", anchor=(100, 100), anchor_size=(2, 2))
    out = place_labels([], [req])
    _, (cx, cy) = out[0].args
    # 'right' candidate centers strictly to the right of the anchor x.
    assert cx > 100
    assert cy == pytest.approx(100)


def test_place_labels_falls_through_priorities():
    """Block the first priority slot with a wide entity — placement
    falls through to a later candidate."""
    # Entity centered to the right of the anchor, blocking 'right'.
    blocker = _entity_entry("Blk", (160, 100))
    req = LabelRequest(text="X", anchor=(100, 100), anchor_size=(2, 2))
    out = place_labels([blocker], [req])
    label_entry = _label_entries(out)[0]
    _, (cx, cy) = label_entry.args
    # Not at 'right' (would be ~cx > 100, cy == 100). Either above, below, or left.
    assert not (cx > 110 and cy == pytest.approx(100))


def _boxed_in_request():
    """An anchor surrounded on all sides so every priority candidate (and the
    small fallback nudges) overlaps an entity bbox."""
    anchor = (300, 300)
    surrounders = [
        _entity_entry("R", (332, 300)),   # right
        _entity_entry("L", (268, 300)),   # left
        _entity_entry("U", (300, 278)),   # above
        _entity_entry("D", (300, 322)),   # below
        _entity_entry("C", (300, 300)),   # center
        _entity_entry("R2", (348, 300)),  # second ring to defeat +8px nudges
        _entity_entry("L2", (252, 300)),
        _entity_entry("U2", (300, 262)),
        _entity_entry("D2", (300, 338)),
    ]
    req = LabelRequest(text="boxed", anchor=anchor, anchor_size=(2, 2))
    return surrounders, req


def test_place_labels_strict_raises_when_all_overlap():
    """With strict_labels=True, a fully boxed-in anchor raises after the
    ladder (shrink + nudge) is exhausted."""
    surrounders, req = _boxed_in_request()
    with pytest.raises(LabelPlacementError) as exc:
        place_labels(surrounders, [req], strict_labels=True)
    assert exc.value.failures == [req]
    # Entries on the exception are the partial list (no successful placements).
    assert all(e.primitive is not _label_primitive for e in exc.value.entries)


def test_place_labels_lenient_overlaps_when_all_overlap():
    """By default (lenient), the same boxed-in anchor lands the label with an
    overlap flag and warns rather than raising."""
    surrounders, req = _boxed_in_request()
    with pytest.warns(UserWarning, match="overlap"):
        out = place_labels(surrounders, [req])
    label = _label_entries(out)[0]
    assert label.kwargs.get("overlap") is True


def test_style_override_does_not_crash():
    """Passing custom label_* style keys works end-to-end."""
    style = {"label_font_family": "Times", "label_font_size": 20, "label_font_color": "#FF0000"}
    req = LabelRequest(text="L", anchor=(100, 100), anchor_size=(2, 2))
    out = place_labels([], [req], style_dict=style)
    label = _label_entries(out)[0]
    assert label.kwargs == {"style_dict": style}
    g = label.primitive(*label.args, **label.kwargs)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

def test_estimate_text_bbox_monotonic():
    short = _estimate_text_bbox("a", 11)
    long = _estimate_text_bbox("aaaaa", 11)
    bigger_font = _estimate_text_bbox("a", 22)
    assert long[0] > short[0]
    assert bigger_font[0] > short[0]
    assert bigger_font[1] > short[1]


# ---------------------------------------------------------------------------
# pathway_label_requests integration
# ---------------------------------------------------------------------------

def test_pathway_label_requests_emits_one_per_labeled_relation():
    """nfkb fixture has 2 relations with labels and 1 without."""
    fig = load_fixture("multi_compartment_translocation.json")
    entries = layout_pathway(fig)
    requests = pathway_label_requests(fig, entries)
    expected = sum(1 for r in fig.relations if r.label)
    assert len(requests) == expected
    assert {r.text for r in requests} == {
        r.label for r in fig.relations if r.label
    }


def test_pathway_label_requests_anchors_at_arrow_midpoint():
    fig = load_fixture("multi_compartment_translocation.json")
    entries = layout_pathway(fig)
    requests = pathway_label_requests(fig, entries)
    arrow_entries = [e for e in entries if e.primitive in RELATION_TO_ARROW.values()]
    by_label = {r.label: a for r, a in zip(fig.relations, arrow_entries) if r.label}
    for req in requests:
        (sx, sy), (ex, ey) = by_label[req.text].args
        assert req.anchor == pytest.approx(((sx + ex) / 2, (sy + ey) / 2))


def test_pathway_label_requests_skips_blank_labels():
    """Relation.label = None or "" emits no LabelRequest."""
    fig = load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    requests = pathway_label_requests(fig, entries)
    # mapk_cascade fixture has no relation labels.
    labeled = sum(1 for r in fig.relations if r.label)
    assert len(requests) == labeled


def test_pathway_integration_renders_relation_labels():
    """Full pipeline: layout_pathway → pathway_label_requests → place_labels."""
    fig = load_fixture("multi_compartment_translocation.json")
    entries = layout_pathway(fig)
    requests = pathway_label_requests(fig, entries)
    out = place_labels(entries, requests)
    new_labels = _label_entries(out)
    assert len(new_labels) == len(requests)
    # Original entries preserved unmodified at the head.
    assert out[: len(entries)] == entries


# ---------------------------------------------------------------------------
# Render-to-PNG (golden seed)
# ---------------------------------------------------------------------------

def test_label_placementrender_entries_to_png():
    fig = load_fixture("multi_compartment_translocation.json")
    entries = layout_pathway(fig)
    requests = pathway_label_requests(fig, entries)
    composed = place_labels(entries, requests)
    out = render_entries_to_png(composed, "label_placement_nfkb.png")
    assert out.exists() and out.stat().st_size > 0
