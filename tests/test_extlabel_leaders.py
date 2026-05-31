"""Bug 5 regression: externalized (rung-4) entity labels get leader lines, and
entity labels are placed before relation labels.

Symptom (stress3): a fit-aware entity whose label can't fit renders an empty
box; the label floated nearby with no visual connection, and because entity
external labels were submitted to place_labels AFTER relation labels, a roaming
relation label could grab the box-adjacent slot (e.g. "load onto sorter" landing
on top of "Fluorescence-activated cell sorting").

This pins:
  1. pathway_label_requests submits `_extlabel` requests before relation labels.
  2. pathway_extlabel_leaders inserts one dashed leader per externalized label,
     connecting the label to its box (edge-to-edge), and is a no-op otherwise.
  3. Leaders are inserted before the first placed label (so the per-panel
     slice in the compositor keeps them grouped with labels).
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
from imageGen.layout.label_placement import _label_primitive, place_labels
from imageGen.layout.pathway_layout import (
    PRIMITIVE_REGISTRY,
    _leader_line,
    layout_pathway,
    pathway_extlabel_leaders,
    pathway_label_requests,
)

_LONG = "Supercalifragilisticexpialidocious extra long entity label"


def _fig_with_external_and_relation() -> Figure:
    return Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="big", type=EntityType.PROTEIN, label=_LONG),
            Entity(id="ok", type=EntityType.PROTEIN, label="ATP"),
        ],
        relations=[
            Relation(source="big", target="ok", type=RelationType.ACTIVATES,
                     label="bind"),
        ],
        compartments=[],
    )


# ---------------------------------------------------------------------------
# Part 1 — request ordering
# ---------------------------------------------------------------------------

def test_external_labels_submitted_before_relation_labels():
    fig = _fig_with_external_and_relation()
    entries = layout_pathway(fig)
    reqs = pathway_label_requests(fig, entries)

    ir_ids = [r.ir_id for r in reqs]
    assert "big_extlabel" in ir_ids, "expected an external label request"
    rel_id = fig.relations[0].ir_id
    assert rel_id in ir_ids, "expected the relation label request"
    # External label must come first so it claims its box-adjacent slot.
    assert ir_ids.index("big_extlabel") < ir_ids.index(rel_id)


# ---------------------------------------------------------------------------
# Part 2 — leader emission
# ---------------------------------------------------------------------------

def test_leader_emitted_for_external_label():
    fig = _fig_with_external_and_relation()
    entries = layout_pathway(fig)
    reqs = pathway_label_requests(fig, entries)
    placed = place_labels(entries, reqs)
    with_leaders = pathway_extlabel_leaders(placed)

    leaders = [e for e in with_leaders if e.primitive is _leader_line]
    assert len(leaders) == 1, "exactly one leader for the single external label"
    leader = leaders[0]
    assert leader.ir_id == "leader_big"

    # Endpoints: one end touches the box, the other touches the label.
    ent_prims = frozenset(PRIMITIVE_REGISTRY.values())
    box_center = next(e.args[1] for e in entries
                      if e.primitive in ent_prims and e.ir_id == "big")
    label_center = next(e.args[1] for e in with_leaders
                        if e.primitive is _label_primitive
                        and e.ir_id == "label_big_extlabel")
    label_exit, box_exit = leader.args

    # Project each endpoint onto the box_center -> label_center axis. A clean
    # edge-to-edge connector has the box endpoint nearer the box (smaller t) and
    # the label endpoint nearer the label (larger t), both strictly interior
    # (the exits sit on the perimeters between the two centers).
    vx = label_center[0] - box_center[0]
    vy = label_center[1] - box_center[1]
    denom = vx * vx + vy * vy
    assert denom > 0, "box and label must not be co-located"

    def _t(p):
        return ((p[0] - box_center[0]) * vx + (p[1] - box_center[1]) * vy) / denom

    t_box, t_label = _t(box_exit), _t(label_exit)
    assert 0.0 < t_box < t_label < 1.0, (
        f"connector endpoints out of order: t_box={t_box:.3f}, t_label={t_label:.3f}"
    )


def test_leader_is_noop_without_external_labels():
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="a", type=EntityType.PROTEIN, label="ATP"),
            Entity(id="b", type=EntityType.PROTEIN, label="ADP"),
        ],
        relations=[Relation(source="a", target="b",
                            type=RelationType.ACTIVATES, label="x")],
        compartments=[],
    )
    entries = layout_pathway(fig)
    reqs = pathway_label_requests(fig, entries)
    placed = place_labels(entries, reqs)
    after = pathway_extlabel_leaders(placed)
    assert after is placed, "no external labels -> input returned unchanged"
    assert not any(e.primitive is _leader_line for e in after)


def test_leaders_inserted_before_first_label():
    """Leaders land at the first-label index so result[:n]/result[n:] slicing
    (the per-panel path) keeps leaders grouped with labels, not with content."""
    fig = _fig_with_external_and_relation()
    entries = layout_pathway(fig)
    reqs = pathway_label_requests(fig, entries)
    placed = place_labels(entries, reqs)
    with_leaders = pathway_extlabel_leaders(placed)

    first_leader_idx = next(i for i, e in enumerate(with_leaders)
                            if e.primitive is _leader_line)
    # No label primitive may appear before the first leader.
    assert not any(
        e.primitive is _label_primitive for e in with_leaders[:first_leader_idx]
    ), "a label was emitted before the leader block"
