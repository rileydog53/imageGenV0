"""LT1 — ring (circular) layout for cyclic compartment-free pathways."""
import math
import warnings

import pytest

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
from imageGen.layout._geom import ENTITY_TO_PRIMITIVE
from imageGen.layout.pathway_layout import (
    RELATION_TO_ARROW,
    _ring_order,
    compute_pathway_canvas,
    layout_pathway,
    pathway_label_requests,
)

from tests._helpers import load_fixture


def _cycle_figure(n: int, *, hint: str | None = None, compartments=None) -> Figure:
    ents = [Entity(id=f"e{i}", type=EntityType.METABOLITE, label=f"E{i}") for i in range(n)]
    rels = [
        Relation(source=f"e{i}", target=f"e{(i + 1) % n}", type=RelationType.GENERIC)
        for i in range(n)
    ]
    return Figure(
        archetype=Archetype.PATHWAY,
        entities=ents,
        relations=rels,
        layout_hint=hint,
        compartments=compartments or [],
    )


def _chain_figure(n: int, *, hint: str | None = None) -> Figure:
    ents = [Entity(id=f"e{i}", type=EntityType.METABOLITE, label=f"E{i}") for i in range(n)]
    rels = [
        Relation(source=f"e{i}", target=f"e{i + 1}", type=RelationType.GENERIC)
        for i in range(n - 1)
    ]
    return Figure(
        archetype=Archetype.PATHWAY, entities=ents, relations=rels, layout_hint=hint
    )


def _entity_pos(entries):
    prims = set(ENTITY_TO_PRIMITIVE.values())
    return {e.ir_id: e.args[1] for e in entries if e.primitive in prims and e.ir_id}


def _centroid(pos):
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    return sum(xs) / len(xs), sum(ys) / len(ys)


# --- detection --------------------------------------------------------------

def test_pure_single_cycle_auto_rings():
    assert _ring_order(_cycle_figure(6)) is not None


def test_two_node_cycle_does_not_ring():
    assert _ring_order(_cycle_figure(2)) is None


def test_linear_chain_does_not_ring():
    assert _ring_order(_chain_figure(5)) is None


def test_layout_hint_forces_ring_on_noncycle():
    # A linear chain isn't a cycle, but the hint forces the ring.
    assert _ring_order(_chain_figure(4, hint="circular")) is not None


def test_ring_order_follows_cycle_adjacency():
    order = _ring_order(_cycle_figure(5))
    # Consecutive ring slots must be adjacent in the cycle e0→e1→…→e4→e0.
    idx = {n: i for i, n in enumerate(order)}
    for i in range(5):
        assert abs(idx[f"e{i}"] - idx[f"e{(i + 1) % 5}"]) in (1, 4)


def test_layout_hint_ignored_with_compartments_warns():
    fig = _cycle_figure(
        4,
        hint="circular",
        compartments=[Compartment(id="c0", type=CompartmentType.CYTOPLASM, label="Cyto")],
    )
    for e in fig.entities:
        e.location = "c0"
    with pytest.warns(UserWarning, match="compartment-free"):
        assert _ring_order(fig) is None


# --- geometry ---------------------------------------------------------------

def test_ring_nodes_are_equidistant_from_centre():
    fig = load_fixture("krebs_cycle.json")
    entries = layout_pathway(fig)
    pos = _entity_pos(entries)
    assert len(pos) == 8
    cx, cy = _centroid(pos)
    radii = [math.hypot(x - cx, y - cy) for x, y in pos.values()]
    assert max(radii) - min(radii) < 1e-6  # exact ring


def test_ring_canvas_is_square():
    fig = load_fixture("krebs_cycle.json")
    w, h = compute_pathway_canvas(fig)
    assert w == h
    # compute_pathway_canvas and layout_pathway must agree on the envelope.
    entries = layout_pathway(fig)
    pos = _entity_pos(entries)
    for x, y in pos.values():
        assert 0 <= x <= w and 0 <= y <= h


def test_ring_arrows_are_straight_chords():
    fig = load_fixture("krebs_cycle.json")
    entries = layout_pathway(fig)
    arrows = [e for e in entries if e.primitive in set(RELATION_TO_ARROW.values())]
    assert len(arrows) == 8
    # No arch / corridor waypoints — every ring arrow is a straight chord.
    assert all(not a.kwargs.get("waypoints") for a in arrows)


def test_ring_emits_no_compartment_band():
    fig = load_fixture("krebs_cycle.json")
    entries = layout_pathway(fig)
    from imageGen.layout.pathway_layout import _compartment_band
    assert not any(e.primitive is _compartment_band for e in entries)


def test_ring_edge_labels_pushed_outside_node_radius():
    fig = load_fixture("krebs_cycle.json")
    entries = layout_pathway(fig)
    pos = _entity_pos(entries)
    cx, cy = _centroid(pos)
    node_r = math.hypot(next(iter(pos.values()))[0] - cx,
                        next(iter(pos.values()))[1] - cy)
    reqs = pathway_label_requests(fig, entries)
    assert len(reqs) == 8
    # Chord midpoints sit at node_r*cos(pi/8); the outward push must move the
    # label anchor strictly farther from centre than that midpoint.
    chord_mid_r = node_r * math.cos(math.pi / 8)
    for r in reqs:
        d = math.hypot(r.anchor[0] - cx, r.anchor[1] - cy)
        assert d > chord_mid_r


def test_linear_fixture_layout_unchanged_by_lt1():
    # A real-compartment pathway must not be touched by ring detection.
    fig = load_fixture("mapk_cascade.json")
    assert _ring_order(fig) is None
