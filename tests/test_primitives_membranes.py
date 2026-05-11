"""Phase 2 Step 3 tests for primitives/membranes.py.

Tests cover:
- DEFAULT_STYLE completeness (all namespaced keys present)
- MembraneCurve.anchor_at() return types and parametric range
- Each public function returns the correct types
- Style override does not crash any function
- Integration: receptor() and gpcr() from proteins.py are anchored via anchor_at()
- Render-to-PNG: one PNG per membrane variant (golden-image seeds for Phase 6)
"""
from __future__ import annotations

import math

import svgwrite
import svgwrite.container

from primitives.membranes import (
    DEFAULT_STYLE,
    MembraneCurve,
    cell_membrane_outline,
    lipid_bilayer,
    nuclear_envelope,
)
from primitives.proteins import gpcr, receptor
from tests._helpers import render_group_to_png


# ---------------------------------------------------------------------------
# DEFAULT_STYLE completeness
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    """All bilayer_*, membrane_*, nuclear_*, and label_* keys must be present."""
    required = {
        "bilayer_outer_stroke", "bilayer_outer_stroke_width",
        "bilayer_inner_stroke", "bilayer_inner_stroke_width",
        "bilayer_head_fill", "bilayer_head_radius",
        "bilayer_tail_fill", "bilayer_tail_stroke",
        "bilayer_head_spacing", "bilayer_thickness",
        "membrane_stroke", "membrane_stroke_width",
        "membrane_fill", "membrane_sample_points",
        "nuclear_outer_stroke", "nuclear_outer_stroke_width",
        "nuclear_inner_stroke", "nuclear_inner_stroke_width",
        "nuclear_gap", "nuclear_pore_fill",
        "nuclear_pore_radius", "nuclear_pore_count",
        "label_font_family", "label_font_size", "label_font_color",
    }
    missing = required - set(DEFAULT_STYLE.keys())
    assert not missing, f"DEFAULT_STYLE missing keys: {missing}"


# ---------------------------------------------------------------------------
# MembraneCurve anchor protocol
# ---------------------------------------------------------------------------

def test_membrane_curve_anchor_at_returns_correct_types():
    """anchor_at() must return ((float, float), float) -- the protein anchor contract."""
    pts = [(math.cos(2 * math.pi * k / 64) * 50 + 50,
            math.sin(2 * math.pi * k / 64) * 50 + 50)
           for k in range(64)]
    curve = MembraneCurve(points=pts, closed=True)
    pos, angle = curve.anchor_at(0.5)
    assert isinstance(pos, tuple) and len(pos) == 2
    assert isinstance(pos[0], float) and isinstance(pos[1], float)
    assert isinstance(angle, float)


def test_membrane_curve_anchor_at_full_parametric_range():
    """anchor_at() must succeed without error at t = 0, 0.25, 0.5, 0.75, 1.0."""
    pts = [(math.cos(2 * math.pi * k / 32) * 40 + 50,
            math.sin(2 * math.pi * k / 32) * 40 + 50)
           for k in range(32)]
    curve = MembraneCurve(points=pts, closed=True)
    for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
        pos, angle = curve.anchor_at(t)
        assert -math.pi <= angle <= math.pi, f"angle out of range at t={t}"


def test_membrane_curve_anchor_at_clamps_out_of_range():
    """Values outside [0, 1] are clamped without raising an exception."""
    pts = [(float(k), 0.0) for k in range(10)]
    curve = MembraneCurve(points=pts, closed=False)
    curve.anchor_at(-0.5)   # should not raise
    curve.anchor_at(1.5)    # should not raise


# ---------------------------------------------------------------------------
# Public function return types
# ---------------------------------------------------------------------------

def test_cell_membrane_outline_circle_returns_group_and_curve():
    """cell_membrane_outline('circle') must return (Group, MembraneCurve)."""
    group, curve = cell_membrane_outline(shape="circle", size=(200.0, 200.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_cell_membrane_outline_irregular_returns_group_and_curve():
    """cell_membrane_outline('irregular') must return (Group, MembraneCurve)."""
    group, curve = cell_membrane_outline(shape="irregular", size=(200.0, 200.0))
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_lipid_bilayer_returns_group():
    """lipid_bilayer() given a circular curve must return a Group."""
    _, curve = cell_membrane_outline(shape="circle", size=(200.0, 200.0))
    group = lipid_bilayer(curve)
    assert isinstance(group, svgwrite.container.Group)


def test_nuclear_envelope_returns_group_and_curve():
    """nuclear_envelope() must return (Group, MembraneCurve)."""
    group, curve = nuclear_envelope(center=(100.0, 100.0), radius=70.0)
    assert isinstance(group, svgwrite.container.Group)
    assert isinstance(curve, MembraneCurve)


def test_style_override_does_not_crash():
    """Passing custom style keys must not crash any public function."""
    override = {"bilayer_head_fill": "#FF0000", "nuclear_pore_fill": "#00FF00"}
    _, curve = cell_membrane_outline(style_dict=override)
    lipid_bilayer(curve, style_dict=override)
    nuclear_envelope(style_dict=override)


# ---------------------------------------------------------------------------
# Integration: protein anchoring via anchor_at()
# ---------------------------------------------------------------------------

def test_receptor_anchored_to_membrane():
    """receptor() can be placed using position + angle from anchor_at()."""
    _, curve = cell_membrane_outline(shape="circle", size=(300.0, 300.0))
    pos, angle = curve.anchor_at(0.25)
    # receptor() accepts (label, position, orientation) -- this is the Phase 3 contract
    g = receptor("EGFR", pos, orientation=angle)
    assert isinstance(g, svgwrite.container.Group)


def test_gpcr_anchored_to_membrane():
    """gpcr() can be placed using position + angle from anchor_at()."""
    _, curve = cell_membrane_outline(shape="circle", size=(300.0, 300.0))
    pos, angle = curve.anchor_at(0.5)
    g = gpcr("beta2AR", pos, orientation=angle)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Render-to-PNG -- golden-image seeds for Phase 6
# ---------------------------------------------------------------------------

def test_membranesrender_group_to_png():
    """Render one PNG per membrane variant; assert each file exists and is non-empty."""
    # Build all renderable groups
    outline_circle_group, circ_curve = cell_membrane_outline(
        shape="circle", size=(260.0, 260.0)
    )
    outline_irregular_group, irr_curve = cell_membrane_outline(
        shape="irregular", size=(260.0, 260.0)
    )
    bilayer_group = lipid_bilayer(circ_curve)
    nuc_group, _ = nuclear_envelope(center=(130.0, 130.0), radius=100.0)

    # Build integration composite: bilayer + receptor anchored at t=0.1
    composite = svgwrite.container.Group()
    composite.add(bilayer_group)
    pos, angle = circ_curve.anchor_at(0.1)
    composite.add(receptor("EGFR", pos, orientation=angle))

    cases: dict[str, tuple[svgwrite.container.Group, tuple[int, int]]] = {
        "membrane_circle_outline.png":    (outline_circle_group,    (280, 280)),
        "membrane_irregular_outline.png": (outline_irregular_group, (280, 280)),
        "membrane_lipid_bilayer.png":     (bilayer_group,           (280, 280)),
        "membrane_nuclear_envelope.png":  (nuc_group,               (280, 280)),
        "membrane_receptor_anchored.png": (composite,               (280, 280)),
    }

    for filename, (group, canvas) in cases.items():
        out = render_group_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"
