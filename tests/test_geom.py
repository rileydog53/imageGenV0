"""Tests for layout/_geom.py — ENTITY_BBOX synchronization and L6 registry.

C5 guard: asserts that ENTITY_BBOX values match each dispatched primitive's
default `size` parameter so any future drift is caught automatically.
"""
import inspect
import warnings

import pytest

from imageGen.ir.schema import Archetype, Entity, EntityType, Figure, Relation, RelationType
from imageGen.layout._geom import (
    ENTITY_BBOX,
    ENTITY_TO_PRIMITIVE,
    PRIMITIVE_REGISTRY,
    PRIMITIVE_TO_BBOX,
)
from imageGen.layout.pathway_layout import layout_pathway


def test_entity_bbox_matches_primitive_defaults():
    """Every entry in ENTITY_BBOX must equal the dispatched primitive's default size.

    When a primitive's default size changes, update _geom.py to match.
    """
    for entity_type, primitive in ENTITY_TO_PRIMITIVE.items():
        sig = inspect.signature(primitive)
        if "size" not in sig.parameters:
            continue
        default_size = sig.parameters["size"].default
        if default_size is inspect.Parameter.empty:
            continue
        expected = tuple(float(x) for x in default_size)
        actual = ENTITY_BBOX[entity_type]
        assert actual == expected, (
            f"ENTITY_BBOX[{entity_type!r}] = {actual} does not match "
            f"{primitive.__name__} default size = {default_size}. "
            f"Update ENTITY_BBOX in layout/_geom.py."
        )


# ---------------------------------------------------------------------------
# V2 / L6: primitive registry tests
# ---------------------------------------------------------------------------

def test_primitive_registry_is_nonempty():
    assert len(PRIMITIVE_REGISTRY) > 0


def test_primitive_registry_all_callables():
    for name, prim in PRIMITIVE_REGISTRY.items():
        assert callable(prim), f"PRIMITIVE_REGISTRY[{name!r}] is not callable"


def test_primitive_to_bbox_covers_registry():
    """Every registered primitive must have an entry in PRIMITIVE_TO_BBOX."""
    for name, prim in PRIMITIVE_REGISTRY.items():
        assert prim in PRIMITIVE_TO_BBOX, (
            f"PRIMITIVE_TO_BBOX missing entry for {name!r}"
        )


def test_primitive_override_renders_kinase_for_protein_entity():
    """A PROTEIN entity with style['primitive']='kinase' must render as kinase."""
    from imageGen.layout._geom import PRIMITIVE_REGISTRY
    from imageGen.layout.types import LayoutEntry
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[Entity(
            id="e1", label="Src", type=EntityType.PROTEIN,
            style={"primitive": "kinase"},
        )],
    )
    entries = layout_pathway(fig)
    entity_entries = [e for e in entries if e.ir_id == "e1"]
    assert entity_entries, "No LayoutEntry for entity e1"
    assert entity_entries[0].primitive is PRIMITIVE_REGISTRY["kinase"]


def test_primitive_override_gene_entity_uses_generic_protein():
    """A GENE entity overridden to 'generic_protein' must render as a rect, not helix."""
    from imageGen.layout._geom import PRIMITIVE_REGISTRY
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[Entity(
            id="g1", label="TP53", type=EntityType.GENE,
            style={"primitive": "generic_protein"},
        )],
    )
    entries = layout_pathway(fig)
    entity_entries = [e for e in entries if e.ir_id == "g1"]
    assert entity_entries
    assert entity_entries[0].primitive is PRIMITIVE_REGISTRY["generic_protein"]


def test_unknown_primitive_override_warns_and_uses_default():
    """An unknown primitive name emits a UserWarning and falls back to the type default."""
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[Entity(
            id="e1", label="X", type=EntityType.PROTEIN,
            style={"primitive": "nonexistent_primitive"},
        )],
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        entries = layout_pathway(fig)
    warns = [x for x in w if "nonexistent_primitive" in str(x.message)]
    assert warns, "Expected a UserWarning for unknown primitive"
    # Falls back to PROTEIN default (generic_protein)
    entity_entries = [e for e in entries if e.ir_id == "e1"]
    assert entity_entries
    assert entity_entries[0].primitive is ENTITY_TO_PRIMITIVE[EntityType.PROTEIN]


def test_no_style_uses_type_default():
    """Entity with no style dict uses the standard ENTITY_TO_PRIMITIVE mapping."""
    fig = Figure(
        archetype=Archetype.PATHWAY,
        entities=[Entity(id="e1", label="Erk", type=EntityType.KINASE)],
    )
    entries = layout_pathway(fig)
    entity_entries = [e for e in entries if e.ir_id == "e1"]
    assert entity_entries
    assert entity_entries[0].primitive is ENTITY_TO_PRIMITIVE[EntityType.KINASE]
