"""Phase 2 Step 5 tests for primitives/cells.py.

Tests cover:
- DEFAULT_STYLE completeness (all namespaced keys present)
- cell_outline returns (Group, MembraneCurve) for all four style variants
- organelle returns Group for all five organelle types
- compose_cell returns Group with organelles
- Style override does not crash any function
- Integration: cell_outline MembraneCurve supports protein anchoring
- Render-to-PNG: one file per variant (golden-image seeds for Phase 6)
"""
from __future__ import annotations

import svgwrite
import svgwrite.container

from imageGenV0.primitives.cells import (
    DEFAULT_STYLE,
    cell_outline,
    compose_cell,
    organelle,
)
from imageGenV0.primitives.membranes import MembraneCurve
from imageGenV0.primitives.proteins import receptor
from tests._helpers import render_group_to_png


# ---------------------------------------------------------------------------
# DEFAULT_STYLE completeness
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    """All cell_*, organelle_*, and label_* keys must be present."""
    required = {
        "cell_stroke", "cell_stroke_width", "cell_fill", "cell_sample_points",
        "organelle_mito_fill", "organelle_mito_stroke", "organelle_mito_stroke_width",
        "organelle_mito_crista_stroke", "organelle_mito_crista_stroke_width",
        "organelle_mito_crista_count",
        "organelle_er_stroke", "organelle_er_stroke_width", "organelle_er_fill",
        "organelle_er_ribosome_fill", "organelle_er_ribosome_radius",
        "organelle_er_ribosome_spacing",
        "organelle_golgi_fill", "organelle_golgi_stroke", "organelle_golgi_stroke_width",
        "organelle_golgi_cisterna_count", "organelle_golgi_cisterna_gap",
        "organelle_lysosome_fill", "organelle_lysosome_stroke",
        "organelle_lysosome_stroke_width",
        "label_font_family", "label_font_size", "label_font_color",
    }
    missing = required - set(DEFAULT_STYLE.keys())
    assert not missing, f"DEFAULT_STYLE missing keys: {missing}"


# ---------------------------------------------------------------------------
# cell_outline: four style variants
# ---------------------------------------------------------------------------

def test_cell_outline_generic_returns_group_and_curve():
    """cell_outline('generic') must return (Group, MembraneCurve)."""
    group, curve = cell_outline("generic", size=(300.0, 300.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_cell_outline_neuron_returns_group_and_curve():
    """cell_outline('neuron') must return (Group, MembraneCurve)."""
    group, curve = cell_outline("neuron", size=(300.0, 300.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_cell_outline_epithelial_returns_group_and_curve():
    """cell_outline('epithelial') must return (Group, MembraneCurve)."""
    group, curve = cell_outline("epithelial", size=(300.0, 300.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_cell_outline_immune_returns_group_and_curve():
    """cell_outline('immune') must return (Group, MembraneCurve)."""
    group, curve = cell_outline("immune", size=(300.0, 300.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


# ---------------------------------------------------------------------------
# organelle: five types
# ---------------------------------------------------------------------------

def test_organelle_mitochondrion_returns_group():
    """organelle('mitochondrion', ...) must return a Group."""
    g = organelle("mitochondrion", (150.0, 150.0), (80.0, 40.0))
    assert isinstance(g, svgwrite.container.Group)


def test_organelle_er_returns_group():
    """organelle('er', ...) must return a Group."""
    g = organelle("er", (150.0, 150.0), (120.0, 40.0))
    assert isinstance(g, svgwrite.container.Group)


def test_organelle_golgi_returns_group():
    """organelle('golgi', ...) must return a Group."""
    g = organelle("golgi", (150.0, 150.0), (100.0, 80.0))
    assert isinstance(g, svgwrite.container.Group)


def test_organelle_lysosome_returns_group():
    """organelle('lysosome', ...) must return a Group."""
    g = organelle("lysosome", (150.0, 150.0), (30.0, 30.0))
    assert isinstance(g, svgwrite.container.Group)


def test_organelle_nucleus_returns_group():
    """organelle('nucleus', ...) must return a Group (delegates to nuclear_envelope)."""
    g = organelle("nucleus", (150.0, 150.0), (100.0, 100.0))
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# compose_cell
# ---------------------------------------------------------------------------

def test_compose_cell_returns_group():
    """compose_cell with organelles must return a Group."""
    organ_list = [
        ("mitochondrion", (180.0, 160.0), (60.0, 30.0)),
        ("lysosome",      (120.0, 200.0), (25.0, 25.0)),
        ("nucleus",       (150.0, 130.0), (80.0, 80.0)),
    ]
    g = compose_cell("generic", organelles=organ_list, size=(300.0, 300.0))
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Style override
# ---------------------------------------------------------------------------

def test_style_override_does_not_crash():
    """Passing custom style keys to all public functions must not raise."""
    override = {
        "cell_stroke":             "#FF0000",
        "organelle_mito_fill":    "#CCFFCC",
        "organelle_golgi_stroke": "#FF8800",
    }
    cell_outline("generic", style_dict=override)
    organelle("mitochondrion", (100.0, 100.0), (60.0, 30.0), style_dict=override)
    organelle("golgi", (100.0, 100.0), (80.0, 60.0), style_dict=override)
    compose_cell("generic", style_dict=override)


# ---------------------------------------------------------------------------
# Integration: protein anchoring via cell_outline MembraneCurve
# ---------------------------------------------------------------------------

def test_cell_outline_curve_supports_protein_anchoring():
    """MembraneCurve from cell_outline can anchor a receptor() from proteins.py."""
    _, curve = cell_outline("generic", size=(300.0, 300.0))
    pos, angle = curve.anchor_at(0.25)
    g = receptor("EGFR", pos, orientation=angle)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Render-to-PNG -- golden-image seeds for Phase 6
# ---------------------------------------------------------------------------

def _build_composed_cell() -> svgwrite.container.Group:
    """Composed cell with nucleus, mitochondrion, ER, Golgi, and lysosome."""
    _, curve = cell_outline("generic", size=(300.0, 300.0))
    pos, angle = curve.anchor_at(0.15)
    protein = receptor("EGFR", pos, orientation=angle)

    return compose_cell(
        "generic",
        organelles=[
            ("nucleus",       (150.0, 130.0), (90.0, 90.0)),
            ("mitochondrion", (200.0, 200.0), (60.0, 30.0)),
            ("er",            (100.0, 195.0), (90.0, 35.0)),
            ("golgi",         (195.0, 155.0), (70.0, 60.0)),
            ("lysosome",      (110.0, 155.0), (24.0, 24.0)),
        ],
        membrane_proteins=[protein],
        size=(300.0, 300.0),
    )


def test_cells_render_to_png():
    """Render one PNG per variant; assert each file exists and is non-empty."""
    cases: dict[str, tuple[svgwrite.container.Group, tuple[int, int]]] = {
        "cell_outline_generic.png":    (cell_outline("generic")[0],    (320, 320)),
        "cell_outline_neuron.png":     (cell_outline("neuron")[0],     (320, 320)),
        "cell_outline_epithelial.png": (cell_outline("epithelial")[0], (320, 320)),
        "cell_outline_immune.png":     (cell_outline("immune")[0],     (320, 320)),
        "organelle_mitochondrion.png": (organelle("mitochondrion", (150.0, 100.0), (120.0, 60.0)), (300, 200)),
        "organelle_er.png":            (organelle("er",            (150.0, 100.0), (240.0, 60.0)), (300, 200)),
        "organelle_golgi.png":         (organelle("golgi",         (150.0, 120.0), (140.0, 100.0)), (300, 240)),
        "organelle_lysosome.png":      (organelle("lysosome",      (100.0, 100.0), (50.0,  50.0)), (200, 200)),
        "organelle_nucleus.png":       (organelle("nucleus",       (150.0, 150.0), (200.0, 200.0)), (300, 300)),
        "composed_cell.png":           (_build_composed_cell(),                                     (320, 320)),
    }

    for filename, (group, canvas) in cases.items():
        out = render_group_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"
