"""Phase 3 Step 1 tests for layout/reaction_layout.py."""
from __future__ import annotations

import pytest
import svgwrite
import svgwrite.container

from ir.schema import (
    Archetype, Entity, EntityType, Figure, ReactionConditions,
    Relation, RelationType,
)
from layout.reaction_layout import (
    DEFAULT_LAYOUT_PARAMS,
    layout_reaction,
)
from layout.types import LayoutEntry
from primitives.chemistry import render_reaction
from tests._helpers import load_fixture, render_group_to_png

ESTERIFICATION_SMILES = {
    "acid": "CC(=O)O",
    "alcohol": "OCC",
    "ester": "CC(=O)OCC",
}


def _make_minimal_reaction(
    *,
    entities: list[tuple[str, str]] | None = None,
    relations: list[Relation] | None = None,
) -> Figure:
    """Build a small REACTION_SCHEME Figure for negative tests."""
    entities = entities or [("a", "Acid"), ("p", "Product")]
    relations = relations or [
        Relation(source="a", target="p", type=RelationType.GENERIC)
    ]
    return Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[
            Entity(id=eid, type=EntityType.METABOLITE, label=label)
            for eid, label in entities
        ],
        relations=relations,
    )


# ---------------------------------------------------------------------------
# Happy path: simple_reaction.json fixture
# ---------------------------------------------------------------------------

def test_layout_returns_single_entry():
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    assert len(entries) == 1
    assert isinstance(entries[0], LayoutEntry)
    assert entries[0].primitive is render_reaction


def test_layout_classifies_reactants_and_products():
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    reactants_smiles, products_smiles = entries[0].args
    assert reactants_smiles == ["CC(=O)O", "OCC"]
    assert products_smiles == ["CC(=O)OCC"]


def test_layout_extracts_conditions():
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    conditions = entries[0].kwargs["conditions"]
    assert conditions == {"above": "H2SO4 (cat.)", "below": "reflux, 80°C"}


def test_layout_uses_default_position_and_molecule_size():
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    assert entries[0].position == DEFAULT_LAYOUT_PARAMS["reaction_origin"]
    assert entries[0].kwargs["molecule_size"] == DEFAULT_LAYOUT_PARAMS["reaction_molecule_size"]


def test_layout_overrides_layout_params():
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(
        fig,
        smiles_map=ESTERIFICATION_SMILES,
        layout_params={"reaction_molecule_size": (200, 150),
                       "reaction_origin": (50.0, 25.0)},
    )
    assert entries[0].kwargs["molecule_size"] == (200, 150)
    assert entries[0].position == (50.0, 25.0)


def test_layout_forwards_style_dict():
    fig = load_fixture("simple_reaction.json")
    style = {"chem_bond_stroke": "#FF0000"}
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES, style_dict=style)
    assert entries[0].kwargs["style_dict"] == style


# ---------------------------------------------------------------------------
# Conditions extraction edge cases
# ---------------------------------------------------------------------------

def test_layout_no_conditions_relation():
    fig = _make_minimal_reaction()
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert entries[0].kwargs["conditions"] is None


def test_layout_yield_pct_falls_to_below_when_no_notes():
    fig = _make_minimal_reaction(relations=[
        Relation(
            source="a", target="p", type=RelationType.GENERIC,
            conditions=ReactionConditions(reagents=["KOH"], yield_pct=92.0),
        ),
    ])
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert entries[0].kwargs["conditions"] == {"above": "KOH", "below": "92%"}


def test_layout_reagents_only():
    fig = _make_minimal_reaction(relations=[
        Relation(
            source="a", target="p", type=RelationType.GENERIC,
            conditions=ReactionConditions(reagents=["Pd/C", "H2"]),
        ),
    ])
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert entries[0].kwargs["conditions"] == {"above": "Pd/C, H2"}


# ---------------------------------------------------------------------------
# Validation / failure modes
# ---------------------------------------------------------------------------

def test_layout_missing_smiles_raises():
    fig = load_fixture("simple_reaction.json")
    with pytest.raises(ValueError, match="smiles_map is missing"):
        layout_reaction(fig, smiles_map={"acid": "CC(=O)O"})  # missing alcohol + ester


def test_layout_wrong_archetype_raises():
    fig = Figure(archetype=Archetype.PATHWAY, entities=[
        Entity(id="x", type=EntityType.GENERIC, label="X"),
    ])
    with pytest.raises(ValueError, match="REACTION_SCHEME"):
        layout_reaction(fig, smiles_map={})


def test_layout_empty_entities_raises():
    fig = Figure(archetype=Archetype.REACTION_SCHEME)
    with pytest.raises(ValueError, match="entities"):
        layout_reaction(fig, smiles_map={})


def test_layout_empty_relations_raises():
    fig = Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[Entity(id="a", type=EntityType.METABOLITE, label="A")],
    )
    with pytest.raises(ValueError, match="relations"):
        layout_reaction(fig, smiles_map={})


def test_layout_intermediate_raises_not_implemented():
    """An entity that is both source and target = multi-step reaction."""
    fig = _make_minimal_reaction(
        entities=[("a", "A"), ("b", "B"), ("c", "C")],
        relations=[
            Relation(source="a", target="b", type=RelationType.GENERIC),
            Relation(source="b", target="c", type=RelationType.GENERIC),
        ],
    )
    with pytest.raises(NotImplementedError, match="Multi-step"):
        layout_reaction(fig, smiles_map={"a": "C", "b": "CC", "c": "CCC"})


# ---------------------------------------------------------------------------
# End-to-end: execute the LayoutEntry and render to PNG
# ---------------------------------------------------------------------------

def test_layout_executes_to_group():
    """Calling the LayoutEntry's primitive with its args/kwargs must produce
    a non-empty Group — proves the engine emits valid renderer instructions."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    e = entries[0]
    g = e.primitive(*e.args, **e.kwargs)
    assert isinstance(g, svgwrite.container.Group)
    dwg = svgwrite.Drawing(size=("800px", "200px"))
    dwg.add(g)
    assert len(dwg.tostring()) > 1000  # has actual content


def test_layout_renders_to_png():
    """Golden seed for Phase 3 → primitives end-to-end integration. Eyeball
    criterion: matches tests/figures/chemistry_reaction_esterification.png
    since v1 layout is a thin translation."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    e = entries[0]
    g = e.primitive(*e.args, **e.kwargs)
    # Renderer wraps in translate(position); replicate that here for fidelity.
    px, py = e.position
    wrapped = svgwrite.container.Group(transform=f"translate({px},{py})")
    wrapped.add(g)
    out = render_group_to_png(wrapped, "layout_reaction_esterification.png",
                              canvas=(800, 200))
    assert out.exists() and out.stat().st_size > 0
