"""Tests for verify/convention_check.py — Phase 6 Step 3.

Covers the happy path on real fixtures (a flat PATHWAY with an inhibition
relation, a multi-panel figure, a skipped REACTION_SCHEME) and the failure
modes: an inhibition drawn with an arrowhead, an inhibition missing its
T-bar, and an entity rendered with the wrong shape for its type.

Happy paths render real fixtures so the actual renderer's output is
exercised. Failure modes pair a hand-built minimal ``Figure`` with a
hand-written SVG — the convention violation `convention_check` is meant to
catch cannot be produced by the (correct) renderer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from imageGen.ir.schema import (
    Archetype,
    Entity,
    EntityType,
    Figure,
    Relation,
    RelationType,
)
from imageGen.render.compositor import render_figure
from imageGen.verify.convention_check import ConventionCheckError, convention_check
from tests._helpers import load_fixture

DRUG_INHIBITION = "drug_inhibition.json"
WORKFLOW = "three_panel_workflow.json"
OXIDATION = "oxidation_reaction.json"

OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


def _render(fixture, dest, smiles_map=None):
    """Render a fixture to `dest`; return the parsed IR Figure."""
    ir = load_fixture(fixture)
    render_figure(ir, dest, smiles_map=smiles_map)
    return ir


def _write_svg(path: Path, body: str) -> Path:
    """Write a minimal standalone SVG whose only content is `body`."""
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
        f"{body}</svg>"
    )
    return path


# ---------------------------------------------------------------------------
# Happy path — real fixtures
# ---------------------------------------------------------------------------


def test_pathway_with_inhibition_passes(tmp_path):
    """The real renderer draws inhibitions with T-bars and shapes by type."""
    svg = tmp_path / "fig.svg"
    ir = _render(DRUG_INHIBITION, svg)
    convention_check(ir, svg)  # no exception


def test_panel_figure_passes(tmp_path):
    svg = tmp_path / "fig.svg"
    ir = _render(WORKFLOW, svg)
    convention_check(ir, svg)  # no exception


def test_reaction_scheme_is_skipped(tmp_path):
    """A REACTION_SCHEME has no per-entity ids — it must pass without error."""
    svg = tmp_path / "fig.svg"
    ir = _render(OXIDATION, svg, smiles_map=OXIDATION_SMILES)
    convention_check(ir, svg)  # no exception


# ---------------------------------------------------------------------------
# Failure mode — inhibition arrows
# ---------------------------------------------------------------------------


def _inhibition_ir() -> Figure:
    """Minimal PATHWAY figure with a single drug→kinase inhibition."""
    return Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="a", type=EntityType.KINASE, label="A"),
            Entity(id="b", type=EntityType.KINASE, label="B"),
        ],
        relations=[Relation(source="a", target="b", type=RelationType.INHIBITS)],
    )


def test_arrowhead_on_inhibition_raises(tmp_path):
    ir = _inhibition_ir()
    svg = _write_svg(
        tmp_path / "fig.svg",
        '<g id="a"><polygon points="0,0 1,0 1,1" /></g>'
        '<g id="b"><polygon points="0,0 1,0 1,1" /></g>'
        '<g id="rel_a_inhibits_b">'
        '<line x1="0" y1="0" x2="10" y2="0" />'
        '<polygon points="10,0 14,2 14,-2" /></g>',
    )
    with pytest.raises(ConventionCheckError) as excinfo:
        convention_check(ir, svg)
    assert excinfo.value.kind == "inhibition_arrow"
    assert excinfo.value.ir_id == "rel_a_inhibits_b"


def test_inhibition_missing_t_bar_raises(tmp_path):
    ir = _inhibition_ir()
    svg = _write_svg(
        tmp_path / "fig.svg",
        '<g id="a"><polygon points="0,0 1,0 1,1" /></g>'
        '<g id="b"><polygon points="0,0 1,0 1,1" /></g>'
        '<g id="rel_a_inhibits_b"><line x1="0" y1="0" x2="10" y2="0" /></g>',
    )
    with pytest.raises(ConventionCheckError) as excinfo:
        convention_check(ir, svg)
    assert excinfo.value.kind == "inhibition_arrow"
    assert excinfo.value.ir_id == "rel_a_inhibits_b"


# ---------------------------------------------------------------------------
# Failure mode — entity shapes
# ---------------------------------------------------------------------------


def test_wrong_entity_shape_raises(tmp_path):
    """A KINASE rendered as a <rect> violates the polygon convention."""
    ir = Figure(
        archetype=Archetype.PATHWAY,
        entities=[
            Entity(id="k1", type=EntityType.KINASE, label="K1"),
            Entity(id="k2", type=EntityType.KINASE, label="K2"),
        ],
    )
    svg = _write_svg(
        tmp_path / "fig.svg",
        '<g id="k1"><polygon points="0,0 1,0 1,1" /></g>'
        '<g id="k2"><rect x="0" y="0" width="10" height="10" /></g>',
    )
    with pytest.raises(ConventionCheckError) as excinfo:
        convention_check(ir, svg)
    assert excinfo.value.kind == "entity_shape"
    assert excinfo.value.ir_id == "k2"


def test_exception_attributes_are_consistent(tmp_path):
    ir = Figure(
        archetype=Archetype.PATHWAY,
        entities=[Entity(id="k1", type=EntityType.KINASE, label="K1")],
    )
    svg = _write_svg(
        tmp_path / "fig.svg",
        '<g id="k1"><rect x="0" y="0" width="10" height="10" /></g>',
    )
    with pytest.raises(ConventionCheckError) as excinfo:
        convention_check(ir, svg)
    exc = excinfo.value
    assert exc.kind == "entity_shape"
    assert exc.ir_id == "k1"
    assert exc.detail and exc.detail in str(exc)
    assert exc.kind in str(exc)


def test_reaction_scheme_entities_not_audited(tmp_path):
    """REACTION_SCHEME entities have no per-entity ids — shapes aren't checked."""
    ir = Figure(
        archetype=Archetype.REACTION_SCHEME,
        entities=[Entity(id="k1", type=EntityType.KINASE, label="K1")],
    )
    svg = _write_svg(
        tmp_path / "fig.svg",
        '<g id="k1"><rect x="0" y="0" width="10" height="10" /></g>',
    )
    convention_check(ir, svg)  # no exception — figure is skipped
