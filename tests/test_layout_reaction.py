"""Phase 3 Step 1 tests for layout/reaction_layout.py."""
from __future__ import annotations

import pytest
import svgwrite
import svgwrite.container

from imageGen.ir.schema import (
    Archetype, Entity, EntityType, Figure, ReactionConditions,
    Relation, RelationType,
)
from imageGen.layout.reaction_layout import (
    REACTION_DEFAULT_PARAMS,
    _block_width,
    _fit_mol_width,
    _is_reversible,
    _molecule_centers,
    _should_stack,
    layout_reaction,
    reaction_label_requests,
)
from imageGen.layout.types import LayoutEntry
from imageGen.primitives.chemistry import render_multistep_reaction, render_reaction
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
    assert entries[0].position == REACTION_DEFAULT_PARAMS["reaction_origin"]
    assert entries[0].kwargs["molecule_size"] == REACTION_DEFAULT_PARAMS["reaction_molecule_size"]


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


def test_layout_linear_chain_renders_as_molecule_sequence():
    """R6: a linear multi-step chain a→b→c renders as one reaction_0 group
    calling render_multistep_reaction with the molecules in chain order."""
    fig = _make_minimal_reaction(
        entities=[("a", "A"), ("b", "B"), ("c", "C")],
        relations=[
            Relation(source="a", target="b", type=RelationType.GENERIC),
            Relation(source="b", target="c", type=RelationType.GENERIC),
        ],
    )
    entries = layout_reaction(fig, smiles_map={"a": "C", "b": "CC", "c": "CCC"})
    assert len(entries) == 1
    assert entries[0].primitive is render_multistep_reaction
    assert entries[0].ir_id == "reaction_0"
    (molecules,) = entries[0].args
    assert molecules == ["C", "CC", "CCC"]  # chain order


def test_layout_nonlinear_multistep_raises_not_implemented():
    """A convergent multi-step graph (a→c, b→c, c→d) is not a linear chain
    and still raises NotImplementedError."""
    fig = _make_minimal_reaction(
        entities=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
        relations=[
            Relation(source="a", target="c", type=RelationType.GENERIC),
            Relation(source="b", target="c", type=RelationType.GENERIC),
            Relation(source="c", target="d", type=RelationType.GENERIC),
        ],
    )
    with pytest.raises(NotImplementedError, match="not a linear chain"):
        layout_reaction(
            fig, smiles_map={"a": "C", "b": "CC", "c": "CCC", "d": "CCCC"}
        )


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


# ---------------------------------------------------------------------------
# V2 / R2: reversible arrows
# ---------------------------------------------------------------------------

def _make_reversible_reaction() -> Figure:
    return Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[
            Entity(id="a", type=EntityType.METABOLITE, label="A"),
            Entity(id="b", type=EntityType.METABOLITE, label="B"),
        ],
        relations=[
            Relation(
                source="a", target="b", type=RelationType.GENERIC,
                conditions=ReactionConditions(reversible=True),
            ),
        ],
    )


def test_is_reversible_returns_true_for_reversible_conditions():
    fig = _make_reversible_reaction()
    assert _is_reversible(fig) is True


def test_is_reversible_returns_false_without_conditions():
    fig = _make_minimal_reaction()
    assert _is_reversible(fig) is False


def test_is_reversible_returns_false_when_reversible_not_set():
    fig = _make_minimal_reaction(relations=[
        Relation(
            source="a", target="p", type=RelationType.GENERIC,
            conditions=ReactionConditions(reagents=["KOH"], reversible=False),
        ),
    ])
    assert _is_reversible(fig) is False


def test_layout_reaction_sets_reversible_kwarg():
    """When IR conditions.reversible=True, the LayoutEntry must carry reversible=True."""
    fig = _make_reversible_reaction()
    entries = layout_reaction(fig, smiles_map={"a": "CC", "b": "CCO"})
    assert entries[0].kwargs.get("reversible") is True


def test_layout_reaction_omits_reversible_kwarg_when_false():
    """When reversible=False, layout_reaction must NOT add reversible to kwargs."""
    fig = _make_minimal_reaction()
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert "reversible" not in entries[0].kwargs


def test_reversible_entry_renders_without_error():
    """Executing a reversible LayoutEntry must produce a valid Group."""
    fig = _make_reversible_reaction()
    entries = layout_reaction(fig, smiles_map={"a": "CC", "b": "CCO"})
    g = entries[0].primitive(*entries[0].args, **entries[0].kwargs)
    assert isinstance(g, svgwrite.container.Group)


def test_reaction_default_params_has_max_width():
    """reaction_max_width must be in REACTION_DEFAULT_PARAMS (V2/R1 guard)."""
    assert "reaction_max_width" in REACTION_DEFAULT_PARAMS
    assert REACTION_DEFAULT_PARAMS["reaction_max_width"] > 0


def test_simple_reaction_honors_reversible_from_fixture():
    """simple_reaction.json has reversible=true — layout must forward it."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    assert entries[0].kwargs.get("reversible") is True


# ---------------------------------------------------------------------------
# V2 / R1: stacking helpers and layout decision
# ---------------------------------------------------------------------------

def test_block_width_single_mol():
    assert _block_width(1, 140.0, 12.0, 18.0) == pytest.approx(140.0)


def test_block_width_two_mols():
    # 2 * 140 + 1 * (2*12 + 18) = 280 + 42 = 322
    assert _block_width(2, 140.0, 12.0, 18.0) == pytest.approx(322.0)


def test_block_width_zero():
    assert _block_width(0, 140.0, 12.0, 18.0) == pytest.approx(0.0)


def test_should_stack_true_when_overcrowded():
    """With 6 reactants + 6 products + standard sizes, total > 800 → must stack."""
    assert _should_stack(6, 6, 140.0, 12.0, 60.0, 18.0, 800.0) is True


def test_should_stack_false_for_simple_reaction():
    """1 reactant + 1 product with standard sizes fits in 800 → no stack."""
    assert _should_stack(1, 1, 140.0, 12.0, 60.0, 18.0, 800.0) is False


def test_layout_reaction_sets_stack_kwarg_when_overflow():
    """A reaction that overflows reaction_max_width must emit stack=True."""
    # 10 reactants of mol_w=140 each: 10*140 = 1400 > 800.
    n = 10
    entities = (
        [Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(n)]
        + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    )
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(n)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(n)}
    smiles["p0"] = "CCO"
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", UserWarning)
        entries = layout_reaction(fig, smiles_map=smiles)
    assert entries[0].kwargs.get("stack") is True


def test_layout_reaction_omits_stack_kwarg_when_fits():
    """A small reaction must NOT set stack in kwargs."""
    fig = _make_minimal_reaction()
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert "stack" not in entries[0].kwargs


def test_layout_reaction_stacked_renders_without_error():
    """A stacked LayoutEntry must execute without raising."""
    n = 10
    entities = (
        [Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(n)]
        + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    )
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(n)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(n)}
    smiles["p0"] = "CCO"
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", UserWarning)
        entries = layout_reaction(fig, smiles_map=smiles)
    g = entries[0].primitive(*entries[0].args, **entries[0].kwargs)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# V2 / R4: per-molecule label requests
# ---------------------------------------------------------------------------

def test_molecule_centers_flat_two_mols():
    """For 1 reactant + 1 product with no stack, centers are on the same y row."""
    centers = _molecule_centers(
        ["r1"], ["p1"],
        mol_w=140.0, mol_h=100.0,
        gap=12.0, arrow_len=60.0, plus_w=18.0,
        top_pad=0.0, stack=False, row_gap=24.0,
    )
    assert "r1" in centers and "p1" in centers
    _, ry = centers["r1"]
    _, py = centers["p1"]
    assert ry == pytest.approx(py)           # same row


def test_molecule_centers_stacked_different_rows():
    """With stack=True, reactant and product must be on different y rows."""
    centers = _molecule_centers(
        ["r1"], ["p1"],
        mol_w=140.0, mol_h=100.0,
        gap=12.0, arrow_len=60.0, plus_w=18.0,
        top_pad=0.0, stack=True, row_gap=24.0,
    )
    _, ry = centers["r1"]
    _, py = centers["p1"]
    assert py > ry + 50.0  # product is below reactant by at least mol_h/2


def test_reaction_label_requests_returns_one_per_entity():
    """reaction_label_requests must emit one LabelRequest per entity."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    requests = reaction_label_requests(fig, entries)
    assert len(requests) == len(fig.entities)


def test_reaction_label_requests_uses_entity_labels():
    """Each LabelRequest.text must match the corresponding entity.label."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    requests = reaction_label_requests(fig, entries)
    labels = {r.text for r in requests}
    entity_labels = {e.label for e in fig.entities}
    assert labels == entity_labels


def test_reaction_label_requests_ir_ids_match_entities():
    """Each LabelRequest.ir_id must be an entity id in the figure."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    requests = reaction_label_requests(fig, entries)
    entity_ids = {e.id for e in fig.entities}
    for req in requests:
        assert req.ir_id in entity_ids


def test_reaction_label_requests_empty_entries():
    """Empty entries list must return empty requests (not raise)."""
    fig = load_fixture("simple_reaction.json")
    requests = reaction_label_requests(fig, [])
    assert requests == []


def test_reaction_label_requests_below_priority():
    """Compound-name labels must prefer 'below' placement over other directions."""
    fig = load_fixture("simple_reaction.json")
    entries = layout_reaction(fig, smiles_map=ESTERIFICATION_SMILES)
    requests = reaction_label_requests(fig, entries)
    for req in requests:
        assert req.priority[0] == "below"


def test_reaction_labels_rendered_in_end_to_end():
    """End-to-end: a rendered SVG must contain each entity label text."""
    from imageGen.render.compositor import render_figure
    import tempfile
    from pathlib import Path as _Path

    fig = load_fixture("simple_reaction.json")
    smiles = {"acid": "CC(=O)O", "alcohol": "CCO", "ester": "CCOC(C)=O"}
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        p = _Path(f.name)
    render_figure(fig, p, smiles_map=smiles, format="svg")
    svg = p.read_text()
    for ent in fig.entities:
        assert ent.label in svg, f"Label {ent.label!r} missing from SVG"
    p.unlink()


# ---------------------------------------------------------------------------
# V2 / R5: per-arrow conditions merge across multiple relations
# ---------------------------------------------------------------------------

def _two_parallel_reactions(
    cond1: ReactionConditions | None,
    cond2: ReactionConditions | None,
) -> tuple[Figure, dict[str, str]]:
    """Two independent A→C and B→D relations — no intermediates."""
    fig = Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[
            Entity(id="a", label="A", type=EntityType.METABOLITE),
            Entity(id="b", label="B", type=EntityType.METABOLITE),
            Entity(id="c", label="C", type=EntityType.METABOLITE),
            Entity(id="d", label="D", type=EntityType.METABOLITE),
        ],
        relations=[
            Relation(source="a", target="c", type=RelationType.GENERIC, conditions=cond1),
            Relation(source="b", target="d", type=RelationType.GENERIC, conditions=cond2),
        ],
    )
    smiles = {"a": "C", "b": "CC", "c": "CCO", "d": "CCCO"}
    return fig, smiles


def test_multi_relation_reagents_merged_into_above():
    """Two relations with different reagents both appear in 'above', comma-separated."""
    fig, smiles = _two_parallel_reactions(
        ReactionConditions(reagents=["HCl"]),
        ReactionConditions(reagents=["NaOH"]),
    )
    entries = layout_reaction(fig, smiles_map=smiles)
    conditions = entries[0].kwargs["conditions"]
    assert conditions is not None
    assert "HCl" in conditions["above"]
    assert "NaOH" in conditions["above"]


def test_multi_relation_notes_merged_into_below():
    """Two relations with notes both appear in 'below', semicolon-separated."""
    fig, smiles = _two_parallel_reactions(
        ReactionConditions(reagents=["A"], notes="0°C"),
        ReactionConditions(reagents=["B"], notes="80°C"),
    )
    entries = layout_reaction(fig, smiles_map=smiles)
    conditions = entries[0].kwargs["conditions"]
    assert "0°C" in conditions["below"]
    assert "80°C" in conditions["below"]


def test_multi_relation_partial_conditions_skips_none_relation():
    """One relation with conditions, one without — only the one with conditions contributes."""
    fig, smiles = _two_parallel_reactions(
        ReactionConditions(reagents=["Pd/C"], notes="H2, 1 atm"),
        None,
    )
    entries = layout_reaction(fig, smiles_map=smiles)
    conditions = entries[0].kwargs["conditions"]
    assert conditions == {"above": "Pd/C", "below": "H2, 1 atm"}


def test_multi_relation_all_without_conditions_returns_none():
    """All relations with conditions=None must produce conditions=None in kwargs."""
    fig, smiles = _two_parallel_reactions(None, None)
    entries = layout_reaction(fig, smiles_map=smiles)
    assert entries[0].kwargs["conditions"] is None


def test_multi_relation_yield_pct_merged_below():
    """Yield % from multiple relations appear in 'below', semicolon-separated."""
    fig, smiles = _two_parallel_reactions(
        ReactionConditions(yield_pct=75.0),
        ReactionConditions(yield_pct=90.0),
    )
    entries = layout_reaction(fig, smiles_map=smiles)
    conditions = entries[0].kwargs["conditions"]
    assert "75%" in conditions["below"]
    assert "90%" in conditions["below"]


def test_single_relation_conditions_unchanged():
    """Single-relation figure behaviour is identical before and after R5 merge logic."""
    fig = _make_minimal_reaction(relations=[
        Relation(
            source="a", target="p", type=RelationType.GENERIC,
            conditions=ReactionConditions(reagents=["H2SO4 (cat.)"], notes="reflux, 80°C"),
        ),
    ])
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert entries[0].kwargs["conditions"] == {"above": "H2SO4 (cat.)", "below": "reflux, 80°C"}


# ---------------------------------------------------------------------------
# V2 / P2: bond-line packing — adaptive molecule width
# ---------------------------------------------------------------------------

def test_p2_default_params_has_min_width():
    assert "reaction_molecule_min_width" in REACTION_DEFAULT_PARAMS
    assert isinstance(REACTION_DEFAULT_PARAMS["reaction_molecule_min_width"], float)


def test_fit_mol_width_uncrowded_returns_default():
    """1 reactant + 1 product on a wide canvas must not shrink mol_w."""
    result = _fit_mol_width(
        n_reactants=1, n_products=1, mol_w=140.0,
        gap=10.0, arrow_len=80.0, plus_w=12.0,
        max_width=800.0, min_mol_w=60.0, stack=False,
    )
    assert result == pytest.approx(140.0)


def test_fit_mol_width_crowded_flat_shrinks():
    """Many mols on a tight canvas must shrink mol_w below default."""
    result = _fit_mol_width(
        n_reactants=4, n_products=4, mol_w=140.0,
        gap=10.0, arrow_len=80.0, plus_w=12.0,
        max_width=400.0, min_mol_w=60.0, stack=False,
    )
    assert result < 140.0
    assert result >= 60.0


def test_fit_mol_width_crowded_stacked_shrinks():
    """Crowded stacked layout must also shrink mol_w to fit each row."""
    result = _fit_mol_width(
        n_reactants=5, n_products=5, mol_w=140.0,
        gap=10.0, arrow_len=80.0, plus_w=12.0,
        max_width=300.0, min_mol_w=60.0, stack=True,
    )
    assert result < 140.0
    assert result >= 60.0


def test_fit_mol_width_clamped_to_min():
    """Extremely crowded: computed width below min must be clamped to min."""
    result = _fit_mol_width(
        n_reactants=20, n_products=20, mol_w=140.0,
        gap=10.0, arrow_len=80.0, plus_w=12.0,
        max_width=200.0, min_mol_w=60.0, stack=False,
    )
    assert result == pytest.approx(60.0)


def test_layout_reaction_molecule_size_shrinks_when_crowded():
    """layout_reaction must pass a smaller molecule_size when 3 reactants crowd a narrow canvas."""
    entities = [
        Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(3)
    ] + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(3)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(3)}
    smiles["p0"] = "CCO"
    default_w = REACTION_DEFAULT_PARAMS["reaction_molecule_size"][0]
    entries = layout_reaction(
        fig, smiles_map=smiles,
        layout_params={"reaction_max_width": 350.0},
    )
    adapted_w = entries[0].kwargs["molecule_size"][0]
    assert adapted_w < default_w


def test_layout_reaction_molecule_size_unchanged_when_uncrowded():
    """A simple 1→1 reaction on a wide canvas must keep the default molecule size."""
    fig = _make_minimal_reaction()
    default_size = REACTION_DEFAULT_PARAMS["reaction_molecule_size"]
    entries = layout_reaction(fig, smiles_map={"a": "CC", "p": "CCO"})
    assert entries[0].kwargs["molecule_size"] == default_size


def test_layout_reaction_height_scales_with_width():
    """When width shrinks, height must scale proportionally (same aspect ratio)."""
    entities = [
        Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(4)
    ] + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(4)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(4)}
    smiles["p0"] = "CCO"
    default_w, default_h = REACTION_DEFAULT_PARAMS["reaction_molecule_size"]
    entries = layout_reaction(
        fig, smiles_map=smiles,
        layout_params={"reaction_max_width": 400.0},
    )
    aw, ah = entries[0].kwargs["molecule_size"]
    if aw < default_w:
        expected_h = round(default_h * (aw / default_w))
        assert abs(ah - expected_h) <= 1  # integer rounding tolerance


def test_layout_reaction_min_width_warn_when_clamped():
    """When adapted width hits the minimum, a UserWarning must be emitted."""
    entities = [
        Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(10)
    ] + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(10)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(10)}
    smiles["p0"] = "CCO"
    with pytest.warns(UserWarning, match="minimum width"):
        layout_reaction(fig, smiles_map=smiles)


def test_layout_reaction_custom_min_width_respected():
    """reaction_molecule_min_width knob must override the 60px default floor."""
    entities = [
        Entity(id=f"r{i}", type=EntityType.METABOLITE, label=f"R{i}") for i in range(10)
    ] + [Entity(id="p0", type=EntityType.METABOLITE, label="P")]
    relations = [
        Relation(source=f"r{i}", target="p0", type=RelationType.GENERIC)
        for i in range(10)
    ]
    fig = Figure(archetype=Archetype.REACTION_SCHEME, entities=entities, relations=relations)
    smiles = {f"r{i}": "CC" for i in range(10)}
    smiles["p0"] = "CCO"
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", UserWarning)
        entries = layout_reaction(
            fig, smiles_map=smiles,
            layout_params={"reaction_molecule_min_width": 40.0},
        )
    assert entries[0].kwargs["molecule_size"][0] >= 40
