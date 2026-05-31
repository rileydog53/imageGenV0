"""Bug 4 regression: same-band skip arrows must arch over intervening entities.

Symptom (stress2_hub): the ATM->p53 phosphorylation arrow drew a flat line
straight through CHK2 instead of arching over it. The Bug 1 position-clamp fix
already repositioned entities so the *exact* fixture now arches, but the
arch-detection hit-test was still brittle: it tested only the body bbox with a
zero margin, so a shaft that grazes an entity by a few pixels (vertical spread
from the layered-DAG topo-y logic) or passes through a long centered label
while clearing the body would NOT arch.

This file pins:
  1. A shaft grazing within `_HIT_TEST_MARGIN` of a body edge still arches.
  2. A shaft passing through a long label's extent (but clearing the body)
     still arches.
  3. End-to-end: an ATM->CHK2->p53 skip topology routes ATM->p53 as an arch.
"""
from __future__ import annotations

from imageGen.ir.schema import (
    Archetype,
    Entity,
    EntityType,
    Figure,
    Relation,
    RelationType,
)
from imageGen.layout._geom import ENTITY_BBOX
from imageGen.layout.pathway_layout import (
    RELATION_TO_ARROW,
    _HIT_TEST_MARGIN,
    _route_same_band_arrows,
    layout_pathway,
)


# ---------------------------------------------------------------------------
# Low-level: _route_same_band_arrows near-miss handling
# ---------------------------------------------------------------------------

def _route_one_skip(
    *,
    mid_type: EntityType,
    mid_label: str,
    mid_center: tuple[float, float],
    src_center: tuple[float, float] = (0.0, 100.0),
    tgt_center: tuple[float, float] = (400.0, 100.0),
) -> dict:
    """Run _route_same_band_arrows for a src->tgt skip over one mid entity.

    Returns the routes dict keyed by relation index. relations[2] is the
    src->tgt skip arrow whose arch/straight decision we assert on.
    """
    entities = {
        "src": Entity(id="src", type=EntityType.KINASE, label="SRC"),
        "mid": Entity(id="mid", type=mid_type, label=mid_label),
        "tgt": Entity(id="tgt", type=EntityType.PROTEIN, label="TGT"),
    }
    relations = [
        Relation(source="src", target="mid", type=RelationType.ACTIVATES),
        Relation(source="mid", target="tgt", type=RelationType.ACTIVATES),
        Relation(source="src", target="tgt", type=RelationType.ACTIVATES),
    ]
    positions = {"src": src_center, "mid": mid_center, "tgt": tgt_center}
    location_map = {"src": "b", "mid": "b", "tgt": "b"}
    bands = {"b": (0.0, 400.0)}
    effective_bbox = dict(ENTITY_BBOX)
    return _route_same_band_arrows(
        relations, positions, entities, bands, location_map,
        effective_bbox, gap=4.0, clearance=12.0, lane_gap=14.0,
    )


def test_skip_arrow_arches_when_shaft_grazes_body_within_margin():
    """Shaft 6px above the intervening body top (a near-miss) still arches."""
    bw, bh = ENTITY_BBOX[EntityType.KINASE]   # (70, 32)
    # Shaft runs at y=100; offset mid downward so its body top sits ~6px below
    # the shaft (a near-miss the zero-margin body test would have missed).
    mid_y = 100.0 + bh / 2 + 6.0
    routes = _route_one_skip(
        mid_type=EntityType.KINASE, mid_label="MID",
        mid_center=(200.0, mid_y),
    )
    assert routes[2] is not None, "near-miss skip arrow should arch, not go straight"


def test_skip_arrow_straight_when_clear_of_margin():
    """Shaft well clear of the intervening body (> margin) routes straight."""
    bw, bh = ENTITY_BBOX[EntityType.KINASE]
    # Push mid far below so even the expanded (margin + label) box misses.
    mid_y = 100.0 + bh / 2 + _HIT_TEST_MARGIN + 40.0
    routes = _route_one_skip(
        mid_type=EntityType.KINASE, mid_label="MID",
        mid_center=(200.0, mid_y),
    )
    assert routes[2] is None, "clear skip arrow should route straight"


def test_skip_arrow_arches_through_long_label_extent():
    """Shaft clears the body but crosses a long centered label -> arches."""
    # Vertical-ish skip: src above, tgt below, mid between them but with its
    # body NARROW (protein, 60px) carrying a WIDE label. The shaft is offset
    # horizontally so it clears the 60px body but crosses the label extent.
    bw, bh = ENTITY_BBOX[EntityType.PROTEIN]   # (60, 30)
    body_half = bw / 2                          # 30
    # Long label "p21 (CDKN1A)" estimates ~79px wide -> half-extent ~40px.
    # Place the vertical shaft at x = mid_x + body_half + 6 (just past the body
    # edge, but inside the label's ~40px half-extent).
    mid_x = 200.0
    shaft_x = mid_x + body_half + 6.0
    routes = _route_one_skip(
        mid_type=EntityType.PROTEIN, mid_label="p21 (CDKN1A)",
        mid_center=(mid_x, 200.0),
        src_center=(shaft_x, 0.0),
        tgt_center=(shaft_x, 400.0),
    )
    assert routes[2] is not None, (
        "skip arrow grazing a long label should arch even though it clears the body"
    )


# ---------------------------------------------------------------------------
# End-to-end: ATM -> CHK2 -> p53 skip topology arches ATM -> p53
# ---------------------------------------------------------------------------

def test_atm_p53_skip_arrow_arches_over_chk2():
    """The classic stress2 skip: ATM->p53 must arch over the intervening CHK2."""
    figure = Figure(
        archetype=Archetype.PATHWAY,
        title="ATM/CHK2/p53 skip",
        entities=[
            Entity(id="atm", type=EntityType.KINASE, label="ATM"),
            Entity(id="chk2", type=EntityType.KINASE, label="CHK2"),
            Entity(id="p53", type=EntityType.PROTEIN, label="p53"),
        ],
        relations=[
            Relation(source="atm", target="chk2", type=RelationType.PHOSPHORYLATES),
            Relation(source="chk2", target="p53", type=RelationType.PHOSPHORYLATES),
            Relation(source="atm", target="p53", type=RelationType.PHOSPHORYLATES),
        ],
    )
    entries = layout_pathway(figure)
    arrow_prims = set(RELATION_TO_ARROW.values())

    atm_p53 = [
        e for e in entries
        if e.primitive in arrow_prims and e.ir_id == "rel_atm_phosphorylates_p53"
    ]
    assert atm_p53, "ATM->p53 arrow entry not found"
    waypoints = atm_p53[0].kwargs.get("waypoints")
    assert waypoints, "ATM->p53 should arch (carry waypoints), not draw a flat line"

    # The arch corridor must clear CHK2's body: every corridor point sits above
    # (smaller y) or below the CHK2 row by more than half its height.
    chk2_entry = next(
        e for e in entries
        if getattr(e, "ir_id", None) == "chk2"
    )
    _label, (chk2_cx, chk2_cy) = chk2_entry.args[:2]
    chk2_half_h = ENTITY_BBOX[EntityType.KINASE][1] / 2
    # Interior corridor points are waypoints[1:-1]; they must clear the body row.
    for (wx, wy) in waypoints[1:-1]:
        assert abs(wy - chk2_cy) >= chk2_half_h, (
            f"arch corridor point y={wy} runs through CHK2 row y={chk2_cy}"
        )
