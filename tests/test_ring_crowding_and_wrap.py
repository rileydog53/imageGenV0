"""Bug 6 regression: ring edge-label decluttering + balanced wrap splits.

Two independent fixes for the Krebs-cycle stress figure:
  * Ring edge labels ("SDH"/"SCS" beside "Succinate") jammed against their
    adjacent ring node. The outward radial nudge was bumped and a tangential
    divergence pass fans apart any genuinely co-located pair.
  * Long labels wrapped lopsidedly, orphaning a <3-char first fragment
    ("a-Ketoglutarate" -> "a-" / "Ketoglutarate"). `_best_two_line_split` now
    prefers breaks leaving both fragments >= 3 chars, falling back to the full
    candidate set only when every break is lopsided (so the label still wraps).
"""
from __future__ import annotations

import math

from imageGen.primitives._text import _MIN_FRAGMENT, _best_two_line_split
from imageGen.layout.pathway_layout import (
    _RING_DIVERGE_PUSH,
    _RING_DIVERGE_THRESHOLD,
    _RING_RADIAL_NUDGE,
    _fan_apart_ring_labels,
)


# ---------------------------------------------------------------------------
# Wrap balance — _best_two_line_split
# ---------------------------------------------------------------------------

def test_balanced_split_preferred_over_tiny_first_fragment():
    """When a balanced break exists, the lopsided tiny-first break is skipped."""
    # "a-b cdefghij": hyphen break -> ("a-", "b cdefghij") has the smaller
    # max-side (9) but orphans "a-"; the space break -> ("a-b", "cdefghij")
    # keeps both fragments >= 3 and must win.
    a, b = _best_two_line_split("a-b cdefghij")
    assert len(a) >= _MIN_FRAGMENT and len(b) >= _MIN_FRAGMENT
    assert (a, b) == ("a-b", "cdefghij")


def test_lopsided_only_break_is_kept():
    """When the only break is lopsided, keep it so the label still wraps
    (escalating to an external leader would be worse)."""
    # "a-Ketoglutarate": the hyphen is the only break point.
    assert _best_two_line_split("a-Ketoglutarate") == ("a-", "Ketoglutarate")


def test_existing_balanced_labels_unchanged():
    assert _best_two_line_split("Succinyl-CoA") == ("Succinyl-", "CoA")
    assert _best_two_line_split("Oxaloacetate") is None


# ---------------------------------------------------------------------------
# Ring divergence — _fan_apart_ring_labels
# ---------------------------------------------------------------------------

def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def test_colocated_ring_labels_fan_apart():
    # Two labels 4px apart at the bottom of the ring (radial pointing down).
    data = [
        ((200.0, 300.0), (0.0, 1.0), ("below",), "A", "relA"),
        ((204.0, 300.0), (0.0, 1.0), ("below",), "B", "relB"),
    ]
    fanned = _fan_apart_ring_labels(data)
    before = _dist(data[0][0], data[1][0])
    after = _dist(fanned[0][0], fanned[1][0])
    assert after > before
    # Each pushed by _RING_DIVERGE_PUSH along its tangent (here ±x).
    assert after == before + 2 * _RING_DIVERGE_PUSH
    # Non-anchor fields are preserved.
    assert [item[4] for item in fanned] == ["relA", "relB"]


def test_far_apart_ring_labels_unchanged():
    # SDH / SCS as actually measured: 94px apart -> beyond the threshold.
    data = [
        ((183.0, 345.7), (-0.5, 0.87), ("left",), "SDH", "relSDH"),
        ((277.0, 345.7), (0.5, 0.87), ("right",), "SCS", "relSCS"),
    ]
    assert _dist(data[0][0], data[1][0]) > _RING_DIVERGE_THRESHOLD
    fanned = _fan_apart_ring_labels(data)
    assert fanned[0][0] == data[0][0]
    assert fanned[1][0] == data[1][0]


def test_fan_apart_noop_for_singleton_and_empty():
    assert _fan_apart_ring_labels([]) == []
    one = [((0.0, 0.0), (1.0, 0.0), ("right",), "X", "relX")]
    assert _fan_apart_ring_labels(one) == one


# ---------------------------------------------------------------------------
# End-to-end: ring edge labels clear their adjacent node
# ---------------------------------------------------------------------------

def test_ring_radial_nudge_increased():
    """The outward nudge is the larger Bug-6 value (regression guard against a
    silent revert to the old 14px crowding)."""
    assert _RING_RADIAL_NUDGE >= 24.0


def test_krebs_ring_edge_labels_clear_succinate_box():
    """In ring mode, the SDH/SCS edge labels sit outside the Succinate body."""
    from imageGen.ir.schema import (
        Archetype, Entity, EntityType, Figure, Relation, RelationType,
    )
    from imageGen.layout._geom import ENTITY_BBOX
    from imageGen.layout.pathway_layout import (
        PRIMITIVE_REGISTRY, layout_pathway, pathway_label_requests,
    )

    labels = ["Citrate", "Isocitrate", "a-Ketoglutarate", "Succinyl-CoA",
              "Succinate", "Fumarate", "Malate", "Oxaloacetate"]
    ids = ["cit", "iso", "akg", "scoa", "suc", "fum", "mal", "oaa"]
    entities = [Entity(id=i, type=EntityType.METABOLITE, label=l)
                for i, l in zip(ids, labels)]
    rels = []
    enzyme = {("scoa", "suc"): "SCS", ("suc", "fum"): "SDH"}
    for a, b in zip(ids, ids[1:] + ids[:1]):
        rels.append(Relation(source=a, target=b, type=RelationType.GENERIC,
                             label=enzyme.get((a, b), "")))
    fig = Figure(archetype=Archetype.PATHWAY, layout_hint="circular",
                 entities=entities, relations=rels, compartments=[])

    entries = layout_pathway(fig)
    ent_prims = frozenset(PRIMITIVE_REGISTRY.values())
    suc_center = next(e.args[1] for e in entries
                      if e.primitive in ent_prims and e.ir_id == "suc")
    bw, bh = ENTITY_BBOX[EntityType.METABOLITE]

    reqs = pathway_label_requests(fig, entries)
    edge = {r.ir_id: r.anchor for r in reqs
            if r.ir_id in ("rel_suc_generic_fum", "rel_scoa_generic_suc")}
    assert edge, "expected SDH/SCS edge-label requests"
    for ir_id, (ax, ay) in edge.items():
        outside = (abs(ax - suc_center[0]) > bw / 2
                   or abs(ay - suc_center[1]) > bh / 2)
        assert outside, f"{ir_id} anchor {ax,ay} inside Succinate box"
