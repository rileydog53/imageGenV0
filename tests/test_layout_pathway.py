"""Phase 3 Step 2 tests for layout/pathway_layout.py."""
from __future__ import annotations

import json
from pathlib import Path

import cairosvg
import pytest
import svgwrite
import svgwrite.container

from ir.schema import (
    Archetype, Compartment, CompartmentType, Entity, EntityType,
    Figure, Relation, RelationType,
)
from layout.pathway_layout import (
    DEFAULT_LAYOUT_PARAMS,
    ENTITY_TO_PRIMITIVE,
    RELATION_TO_ARROW,
    _compartment_band,
    layout_pathway,
)
from layout.reaction_layout import LayoutEntry
from primitives import arrows, proteins

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIGURES_DIR = Path(__file__).parent / "figures"


def _load_fixture(name: str) -> Figure:
    return Figure.model_validate(json.loads((FIXTURES_DIR / name).read_text()))


def _render_to_png(
    entries: list[LayoutEntry],
    filename: str,
    canvas: tuple[int, int] = (800, 600),
) -> Path:
    w, h = canvas
    dwg = svgwrite.Drawing(size=(f"{w}px", f"{h}px"))
    dwg.add(dwg.rect(insert=(0, 0), size=(f"{w}px", f"{h}px"), fill="white"))
    for e in entries:
        g = e.primitive(*e.args, **e.kwargs)
        px, py = e.position
        if (px, py) != (0.0, 0.0):
            wrap = svgwrite.container.Group(transform=f"translate({px},{py})")
            wrap.add(g)
            dwg.add(wrap)
        else:
            dwg.add(g)
    FIGURES_DIR.mkdir(exist_ok=True)
    out = FIGURES_DIR / filename
    out.write_bytes(cairosvg.svg2png(bytestring=dwg.tostring().encode("utf-8")))
    return out


def _entity_entries(entries: list[LayoutEntry]) -> list[LayoutEntry]:
    return [e for e in entries if e.primitive in ENTITY_TO_PRIMITIVE.values()]


def _arrow_entries(entries: list[LayoutEntry]) -> list[LayoutEntry]:
    return [e for e in entries if e.primitive in RELATION_TO_ARROW.values()]


def _band_entries(entries: list[LayoutEntry]) -> list[LayoutEntry]:
    return [e for e in entries if e.primitive is _compartment_band]


def _band_geom(entry: LayoutEntry) -> tuple[str, float, float, float, float]:
    """(label, x, y, w, h) for a _compartment_band LayoutEntry."""
    label, x, y, w, h = entry.args
    return label, x, y, w, h


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_wrong_archetype_raises():
    fig = Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[Entity(id="x", type=EntityType.GENERIC, label="X")],
    )
    with pytest.raises(ValueError, match="PATHWAY"):
        layout_pathway(fig)


def test_empty_entities_raises():
    fig = Figure(archetype=Archetype.PATHWAY)
    with pytest.raises(ValueError, match="entities"):
        layout_pathway(fig)


# ---------------------------------------------------------------------------
# Compartment ordering and bands
# ---------------------------------------------------------------------------

def test_no_compartments_uses_implicit_band():
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    bands = _band_entries(entries)
    assert len(bands) == 1
    label, *_ = _band_geom(bands[0])
    assert label == ""


def test_compartments_use_ir_declaration_order():
    fig = _load_fixture("gpcr_signaling.json")
    bands = [_band_geom(b) for b in _band_entries(layout_pathway(fig))]
    assert [label for label, *_ in bands] == [
        "Extracellular", "Plasma membrane", "Cytoplasm"
    ]
    ys = [y for _, _, y, _, _ in bands]
    assert ys == sorted(ys)


def test_compartment_bands_partition_canvas():
    fig = _load_fixture("gpcr_signaling.json")
    canvas_h = 600.0
    entries = layout_pathway(fig, layout_params={"pathway_canvas": (800.0, canvas_h)})
    bands = [_band_geom(b) for b in _band_entries(entries)]
    for (_, _, prev_y, _, prev_h), (_, _, nxt_y, _, _) in zip(bands, bands[1:]):
        assert prev_y + prev_h == pytest.approx(nxt_y)
    assert sum(h for _, _, _, _, h in bands) == pytest.approx(canvas_h)


# ---------------------------------------------------------------------------
# Entity placement
# ---------------------------------------------------------------------------

def test_entities_snap_into_their_compartment_band():
    fig = _load_fixture("gpcr_signaling.json")
    entries = layout_pathway(fig)
    bands_by_label: dict[str, tuple[float, float]] = {
        label: (y, y + h) for label, _, y, _, h in map(_band_geom, _band_entries(entries))
    }
    location_to_label = {c.id: c.label for c in fig.compartments}
    for ent in fig.entities:
        match = next(
            e for e in _entity_entries(entries) if e.args[0] == ent.label
        )
        _, (_, y) = match.args
        top, bottom = bands_by_label[location_to_label[ent.location]]
        assert top <= y <= bottom


def test_isolated_entity_still_placed():
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="solo", type=EntityType.PROTEIN, label="Solo"),
        ],
    )
    entries = layout_pathway(fig)
    ents = _entity_entries(entries)
    assert len(ents) == 1
    label, (x, y) = ents[0].args
    assert label == "Solo"
    # placed somewhere on the canvas
    assert 0 <= x <= 800
    assert 0 <= y <= 600


def test_layout_is_deterministic():
    fig = _load_fixture("gpcr_signaling.json")
    a = layout_pathway(fig)
    b = layout_pathway(fig)
    a_pos = [e.args for e in _entity_entries(a)]
    b_pos = [e.args for e in _entity_entries(b)]
    assert a_pos == b_pos


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

def test_entity_dispatch_covers_all_entity_types():
    missing = set(EntityType) - set(ENTITY_TO_PRIMITIVE.keys())
    assert not missing, f"Unmapped EntityTypes: {missing}"


def test_relation_dispatch_covers_all_relation_types():
    missing = set(RelationType) - set(RELATION_TO_ARROW.keys())
    assert not missing, f"Unmapped RelationTypes: {missing}"


def test_phosphorylates_uses_activation_arrow():
    assert RELATION_TO_ARROW[RelationType.PHOSPHORYLATES] is arrows.activation_arrow


def test_entity_type_routes_to_specific_primitive():
    assert ENTITY_TO_PRIMITIVE[EntityType.KINASE] is proteins.kinase
    assert ENTITY_TO_PRIMITIVE[EntityType.RECEPTOR] is proteins.receptor
    assert ENTITY_TO_PRIMITIVE[EntityType.LIGAND] is proteins.generic_protein


# ---------------------------------------------------------------------------
# LayoutEntry shape
# ---------------------------------------------------------------------------

def test_layout_returns_layout_entries():
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    assert entries
    assert all(isinstance(e, LayoutEntry) for e in entries)


def test_one_entity_entry_per_entity():
    fig = _load_fixture("gpcr_signaling.json")
    entries = layout_pathway(fig)
    assert len(_entity_entries(entries)) == len(fig.entities)


def test_relations_emit_layout_entries():
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    assert len(_arrow_entries(entries)) == len(fig.relations)


def test_layout_entries_are_executable():
    fig = _load_fixture("gpcr_signaling.json")
    entries = layout_pathway(fig)
    for entry in entries:
        g = entry.primitive(*entry.args, **entry.kwargs)
        assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Param + style overrides
# ---------------------------------------------------------------------------

def test_layout_params_override_seed_and_canvas():
    fig = _load_fixture("mapk_cascade.json")
    a = layout_pathway(fig, layout_params={"pathway_seed": 1})
    b = layout_pathway(fig, layout_params={"pathway_seed": 2})
    a_pos = [e.args[1] for e in _entity_entries(a)]
    b_pos = [e.args[1] for e in _entity_entries(b)]
    # different seed → at least one entity ordering differs
    assert a_pos != b_pos or len(fig.entities) <= 1

    big = layout_pathway(fig, layout_params={"pathway_canvas": (1600.0, 1200.0)})
    _, _, _, w, _ = _band_geom(_band_entries(big)[0])
    assert w == 1600.0


def test_style_dict_forwarded_to_entity_and_arrow_primitives():
    fig = _load_fixture("gpcr_signaling.json")
    style = {"protein_fill": "#FF0000"}
    entries = layout_pathway(fig, style_dict=style)
    for e in _entity_entries(entries) + _arrow_entries(entries):
        assert e.kwargs.get("style_dict") == style


def test_band_visual_overrides_via_layout_params():
    """Band visuals (fill/stroke/label) live in layout_params, not style_dict —
    layout_params overrides must reach _compartment_band."""
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig, layout_params={"pathway_band_fill": "#ABCDEF"})
    band = _band_entries(entries)[0]
    assert band.kwargs["params"]["pathway_band_fill"] == "#ABCDEF"


def test_default_style_dict_not_forwarded_when_none():
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    for e in _entity_entries(entries) + _arrow_entries(entries):
        assert "style_dict" not in e.kwargs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_cycle_does_not_crash():
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="a", type=EntityType.PROTEIN, label="A"),
            Entity(id="b", type=EntityType.PROTEIN, label="B"),
        ],
        relations=[
            Relation(source="a", target="b", type=RelationType.ACTIVATES),
            Relation(source="b", target="a", type=RelationType.ACTIVATES),
        ],
    )
    entries = layout_pathway(fig)
    assert len(_arrow_entries(entries)) == 2


def test_default_layout_params_keys_are_namespaced():
    """Mirrors the locked-in 'flat namespaced keys' template."""
    for key in DEFAULT_LAYOUT_PARAMS:
        assert key.startswith("pathway_"), f"non-namespaced key: {key}"


# ---------------------------------------------------------------------------
# Render-to-PNG (golden seeds)
# ---------------------------------------------------------------------------

def test_render_mapk_cascade_to_png():
    fig = _load_fixture("mapk_cascade.json")
    entries = layout_pathway(fig)
    out = _render_to_png(entries, "layout_pathway_mapk.png")
    assert out.exists() and out.stat().st_size > 0


def test_render_gpcr_signaling_to_png():
    fig = _load_fixture("gpcr_signaling.json")
    entries = layout_pathway(fig)
    out = _render_to_png(entries, "layout_pathway_gpcr.png")
    assert out.exists() and out.stat().st_size > 0


def test_render_nfkb_translocation_to_png():
    fig = _load_fixture("multi_compartment_translocation.json")
    entries = layout_pathway(fig)
    out = _render_to_png(entries, "layout_pathway_nfkb.png")
    assert out.exists() and out.stat().st_size > 0
