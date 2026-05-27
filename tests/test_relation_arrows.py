"""Tests for the v2.x expansion relation arrows.

Covers the four new arrow primitives (catalysis, cleavage, transport,
recruitment), their RelationType dispatch, and an end-to-end render that
passes the verifiers.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
import svgwrite
import svgwrite.container

from imageGen.ir.schema import Entity, EntityType, Figure, Relation, RelationType
from imageGen.layout.pathway_layout import RELATION_TO_ARROW
from imageGen.primitives import arrows
from imageGen.render.compositor import render_figure
from imageGen.verify.convention_check import convention_check
from imageGen.verify.semantic_check import semantic_check

NEW_ARROWS = [
    arrows.catalysis_arrow,
    arrows.cleavage_arrow,
    arrows.transport_arrow,
    arrows.recruitment_arrow,
]


def _tags(group: svgwrite.container.Group) -> list[str]:
    d = svgwrite.Drawing(size=(240, 120))
    d.add(group)
    root = ET.fromstring(d.tostring())
    return [el.tag.split("}")[-1] for el in root.iter()]


@pytest.mark.parametrize("fn", NEW_ARROWS)
def test_arrow_returns_group_straight(fn):
    assert isinstance(fn((10, 10), (100, 10)), svgwrite.container.Group)


@pytest.mark.parametrize("fn", NEW_ARROWS)
def test_arrow_returns_group_waypoints(fn):
    g = fn((10, 10), (100, 60), waypoints=[(10, 10), (10, 60), (100, 60)])
    assert isinstance(g, svgwrite.container.Group)


def test_dispatch_covers_every_relation_type():
    """Every RelationType must map to an arrow, or layout will KeyError."""
    for rt in RelationType:
        assert rt in RELATION_TO_ARROW, f"{rt} missing from RELATION_TO_ARROW"


def test_catalysis_has_open_circle_not_triangle():
    tags = _tags(arrows.catalysis_arrow((10, 10), (100, 10)))
    assert "circle" in tags
    assert "polygon" not in tags  # not a triangular head


def test_transport_is_block_polygon():
    assert "polygon" in _tags(arrows.transport_arrow((10, 10), (100, 10)))


def test_recruitment_shaft_is_dashed():
    d = svgwrite.Drawing(size=(240, 120))
    d.add(arrows.recruitment_arrow((10, 10), (100, 10)))
    root = ET.fromstring(d.tostring())
    assert any(el.get("stroke-dasharray") for el in root.iter())


def test_new_relations_render_and_pass_verifiers(tmp_path):
    figure = Figure(
        archetype="pathway",
        entities=[
            Entity(id="enz", type=EntityType.KINASE, label="Enzyme"),
            Entity(id="sub", type=EntityType.PROTEIN, label="Substrate"),
            Entity(id="car", type=EntityType.METABOLITE, label="Cargo"),
            Entity(id="dst", type=EntityType.ORGANELLE, label="Membrane"),
        ],
        relations=[
            Relation(source="enz", target="sub", type=RelationType.CATALYZES),
            Relation(source="sub", target="car", type=RelationType.CLEAVES),
            Relation(source="car", target="dst", type=RelationType.TRANSPORTS),
            Relation(source="dst", target="enz", type=RelationType.RECRUITS),
        ],
    )
    out = tmp_path / "rel.png"
    render_figure(figure, str(out))
    svg = tmp_path / "rel.svg"
    semantic_check(figure, str(svg))
    convention_check(figure, str(svg))
