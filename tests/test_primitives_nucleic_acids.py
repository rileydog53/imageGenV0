"""Phase 2 Step 4 tests for primitives/nucleic_acids.py.

Tests cover:
- DEFAULT_STYLE completeness (all namespaced keys present)
- Each public function returns Group under all supported parameter combinations
- Style override does not crash any function
- Integration: dna_segment and rna_segment composed on the same Drawing
- Render-to-PNG: one file per variant (golden-image seeds for Phase 6)
"""
from __future__ import annotations

import svgwrite
import svgwrite.container

import re

from imageGen.primitives.nucleic_acids import (
    DEFAULT_STYLE,
    chromatin,
    dna_segment,
    gene_helix,
    rna_helix,
    rna_segment,
)
from tests._helpers import render_group_to_png


def _polyline_x_coords(svg: str) -> list[float]:
    """All x-coordinates from every <polyline points="..."> in the SVG."""
    xs: list[float] = []
    for pts in re.findall(r'points="([^"]+)"', svg):
        for pair in pts.split():
            xs.append(float(pair.split(",")[0]))
    return xs


# ---------------------------------------------------------------------------
# DEFAULT_STYLE completeness
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    """All dna_*, rna_*, chromatin_*, and label_* keys must be present."""
    required = {
        "dna_strand1_stroke", "dna_strand2_stroke", "dna_strand_stroke_width",
        "dna_amplitude", "dna_period", "dna_sample_rate",
        "dna_rung_stroke", "dna_rung_stroke_width",
        "dna_rung_at_fill", "dna_rung_gc_fill",
        "dna_base_label_font_size", "dna_base_label_show",
        "rna_stroke", "rna_stroke_width",
        "rna_amplitude", "rna_period", "rna_sample_rate",
        "chromatin_backbone_stroke", "chromatin_backbone_stroke_width",
        "chromatin_nucleosome_fill", "chromatin_nucleosome_stroke",
        "chromatin_nucleosome_stroke_width", "chromatin_nucleosome_radius",
        "chromatin_nucleosome_spacing",
        "chromatin_fiber_fill", "chromatin_fiber_stroke",
        "chromatin_fiber_stroke_width", "chromatin_fiber_width",
        "label_font_family", "label_font_size", "label_font_color",
    }
    missing = required - set(DEFAULT_STYLE.keys())
    assert not missing, f"DEFAULT_STYLE missing keys: {missing}"


# ---------------------------------------------------------------------------
# dna_segment return types and parameter variants
# ---------------------------------------------------------------------------

def test_dna_segment_double_helix_returns_group():
    """dna_segment with double_helix=True must return a Group."""
    g = dna_segment((20.0, 100.0), (380.0, 100.0), double_helix=True)
    assert isinstance(g, svgwrite.container.Group)


def test_dna_segment_single_strand_returns_group():
    """dna_segment with double_helix=False must return a Group (ssDNA, no rungs)."""
    g = dna_segment((20.0, 100.0), (380.0, 100.0), double_helix=False)
    assert isinstance(g, svgwrite.container.Group)


def test_dna_segment_supercoiled_returns_group():
    """dna_segment with supercoiled=True must return a Group."""
    g = dna_segment((20.0, 100.0), (380.0, 100.0), supercoiled=True)
    assert isinstance(g, svgwrite.container.Group)


def test_dna_segment_with_sequence_returns_group():
    """dna_segment with a sequence string must return a Group with labeled rungs."""
    g = dna_segment((20.0, 100.0), (380.0, 100.0), sequence="ATGCATGC")
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# rna_segment return types
# ---------------------------------------------------------------------------

def test_rna_segment_single_strand_returns_group():
    """rna_segment with single_strand=True (default) must return a Group."""
    g = rna_segment((20.0, 100.0), (380.0, 100.0), single_strand=True)
    assert isinstance(g, svgwrite.container.Group)


def test_rna_segment_double_stranded_returns_group():
    """rna_segment with single_strand=False (dsRNA) must return a Group."""
    g = rna_segment((20.0, 100.0), (380.0, 100.0), single_strand=False)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# chromatin return types and condensation levels
# ---------------------------------------------------------------------------

def test_chromatin_condensation_zero_returns_group():
    """chromatin at level=0 (beads-on-string) must return a Group."""
    g = chromatin(((20.0, 100.0), (380.0, 100.0)), condensation_level=0.0)
    assert isinstance(g, svgwrite.container.Group)


def test_chromatin_condensation_one_returns_group():
    """chromatin at level=1 (condensed fiber) must return a Group."""
    g = chromatin(((20.0, 100.0), (380.0, 100.0)), condensation_level=1.0)
    assert isinstance(g, svgwrite.container.Group)


def test_chromatin_condensation_mid_returns_group():
    """chromatin at level=0.5 (intermediate) must return a Group."""
    g = chromatin(((20.0, 100.0), (380.0, 100.0)), condensation_level=0.5)
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Style override
# ---------------------------------------------------------------------------

def test_style_override_does_not_crash():
    """Passing custom style keys to all public functions must not raise."""
    override = {
        "dna_strand1_stroke":        "#FF0000",
        "rna_stroke":                "#00CC00",
        "chromatin_nucleosome_fill": "#0000FF",
        "dna_rung_at_fill":          "#FF6600",
    }
    dna_segment((20.0, 100.0), (380.0, 100.0), style_dict=override)
    rna_segment((20.0, 100.0), (380.0, 100.0), style_dict=override)
    chromatin(((20.0, 100.0), (380.0, 100.0)), style_dict=override)


# ---------------------------------------------------------------------------
# Integration: composing dna_segment + rna_segment on the same Drawing
# ---------------------------------------------------------------------------

def test_dna_rna_composable():
    """dna_segment and rna_segment outputs can be added to the same Drawing."""
    dna = dna_segment((20.0, 100.0), (380.0, 100.0))
    # RNA branch emerging from the midpoint -- standard transcription convention
    rna = rna_segment((200.0, 100.0), (380.0, 160.0))

    dwg = svgwrite.Drawing(size=("400px", "200px"))
    dwg.add(dna)
    dwg.add(rna)
    svg_str = dwg.tostring()
    assert len(svg_str) > 0


# ---------------------------------------------------------------------------
# Render-to-PNG -- golden-image seeds for Phase 6
# ---------------------------------------------------------------------------

def _build_chromatin_composite() -> svgwrite.container.Group:
    """Three chromatin segments at levels 0, 0.5, 1 for side-by-side comparison."""
    outer = svgwrite.container.Group()
    for i, level in enumerate([0.0, 0.5, 1.0]):
        y = float(40 + i * 55)
        outer.add(chromatin(((20.0, y), (380.0, y)), condensation_level=level))
    return outer


def test_nucleic_acidsrender_group_to_png():
    """Render one PNG per variant; assert each file exists and is non-empty."""
    cases: dict[str, svgwrite.container.Group] = {
        "dna_double_helix.png":  dna_segment((20.0, 100.0), (380.0, 100.0)),
        "dna_with_sequence.png": dna_segment((20.0, 100.0), (380.0, 100.0),
                                             sequence="ATGCATGC"),
        "dna_single_strand.png": dna_segment((20.0, 100.0), (380.0, 100.0),
                                             double_helix=False),
        "dna_supercoiled.png":   dna_segment((20.0, 100.0), (380.0, 100.0),
                                             supercoiled=True),
        "rna_single.png":        rna_segment((20.0, 100.0), (380.0, 100.0)),
        "rna_dsrna.png":         rna_segment((20.0, 100.0), (380.0, 100.0),
                                             single_strand=False),
        "chromatin_composite.png": _build_chromatin_composite(),
    }

    for filename, group in cases.items():
        canvas = (400, 200) if "chromatin_composite" not in filename else (400, 210)
        out = render_group_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"


# ---------------------------------------------------------------------------
# gene_helix tests
# ---------------------------------------------------------------------------

def test_gene_helix_returns_group():
    """gene_helix must return a Group."""
    g = gene_helix("TP53", (40.0, 20.0))
    assert isinstance(g, svgwrite.container.Group)


def test_gene_helix_custom_size_returns_group():
    """gene_helix with an explicit size must return a Group."""
    g = gene_helix("BRCA1", (60.0, 30.0), size=(100.0, 50.0))
    assert isinstance(g, svgwrite.container.Group)


def test_gene_helix_style_override_does_not_crash():
    """gene_helix accepts style overrides without raising."""
    g = gene_helix("MYC", (40.0, 20.0), style_dict={"dna_strand1_stroke": "#FF0000"})
    assert isinstance(g, svgwrite.container.Group)


def test_gene_helix_color_param_accepted():
    """gene_helix accepts color kwarg for API parity with generic_protein; no crash."""
    g = gene_helix("KRAS", (40.0, 20.0), color="#AABBCC")
    assert isinstance(g, svgwrite.container.Group)


def test_gene_helix_render_to_png():
    """gene_helix renders to a non-empty PNG."""
    g = gene_helix("TP53", (40.0, 20.0))
    out = render_group_to_png(g, "gene_helix.png", canvas=(80, 40))
    assert out.exists(), f"PNG not written: {out}"
    assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"


# ---------------------------------------------------------------------------
# LT7 — broken DNA (double-strand break)
# ---------------------------------------------------------------------------

def test_broken_dna_segment_returns_group():
    g = dna_segment((0.0, 50.0), (200.0, 50.0), broken=True)
    assert isinstance(g, svgwrite.container.Group)


def test_broken_dna_has_coordinate_gap_on_both_strands():
    """A break centred at 0.5 must leave a strand-free axis gap there."""
    g = dna_segment((0.0, 50.0), (200.0, 50.0), broken=True,
                    style_dict={"dna_break_gap": 20.0})
    xs = _polyline_x_coords(g.tostring())
    # Break centred at x=100 with a 20px gap → no strand point in (90, 110).
    assert xs, "expected strand polylines"
    assert not [x for x in xs if 90.0 < x < 110.0]
    # Strands still span both flanks.
    assert min(xs) < 90.0 and max(xs) > 110.0


def test_broken_dna_break_position_shifts_gap():
    g = dna_segment((0.0, 50.0), (200.0, 50.0), broken=True, break_position=0.25,
                    style_dict={"dna_break_gap": 20.0})
    xs = _polyline_x_coords(g.tostring())
    # Gap now around x=50; no strand points in (40, 60), but present around 100.
    assert not [x for x in xs if 40.0 < x < 60.0]
    assert [x for x in xs if 90.0 < x < 110.0]


def test_unbroken_dna_has_no_gap():
    """Regression: a normal segment is continuous across the midpoint."""
    g = dna_segment((0.0, 50.0), (200.0, 50.0))
    xs = _polyline_x_coords(g.tostring())
    assert [x for x in xs if 90.0 < x < 110.0]


def test_gene_helix_broken_via_param():
    g = gene_helix("DSB", (100.0, 100.0), size=(120.0, 40.0), broken=True)
    xs = _polyline_x_coords(g.tostring())
    # Helix spans roughly [46, 154]; centre break leaves a gap near x=100.
    assert xs and not [x for x in xs if 96.0 < x < 104.0]


def test_gene_helix_broken_via_style_key():
    g = gene_helix("DSB", (100.0, 100.0), size=(120.0, 40.0),
                   style_dict={"dna_break": True})
    xs = _polyline_x_coords(g.tostring())
    assert xs and not [x for x in xs if 96.0 < x < 104.0]


# ---------------------------------------------------------------------------
# LT8 — RNA entity primitive (rna_helix)
# ---------------------------------------------------------------------------

def test_rna_helix_returns_group():
    assert isinstance(rna_helix("sgRNA", (100.0, 100.0)), svgwrite.container.Group)


def test_rna_helix_is_orange_not_dna_blue():
    svg = rna_helix("sgRNA", (100.0, 100.0)).tostring().upper()
    assert "E65100" in svg              # RNA orange
    assert "1565C0" not in svg          # not DNA strand-1 blue


def test_rna_helix_renders_label():
    svg = rna_helix("miR-21", (100.0, 100.0)).tostring()
    assert "miR-21" in svg


def test_rna_helix_render_to_png():
    g = rna_helix("sgRNA", (40.0, 20.0))
    out = render_group_to_png(g, "rna_helix.png", canvas=(80, 40))
    assert out.exists() and out.stat().st_size > 100
