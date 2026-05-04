"""Phase 2 Step 4 tests for primitives/nucleic_acids.py.

Tests cover:
- DEFAULT_STYLE completeness (all namespaced keys present)
- Each public function returns Group under all supported parameter combinations
- Style override does not crash any function
- Integration: dna_segment and rna_segment composed on the same Drawing
- Render-to-PNG: one file per variant (golden-image seeds for Phase 6)
"""
from __future__ import annotations

from pathlib import Path

import cairosvg
import svgwrite
import svgwrite.container

from primitives.nucleic_acids import (
    DEFAULT_STYLE,
    chromatin,
    dna_segment,
    rna_segment,
)

FIGURES_DIR = Path(__file__).parent / "figures"


def _render_to_png(
    group: svgwrite.container.Group,
    filename: str,
    canvas: tuple[int, int] = (400, 200),
) -> Path:
    """Wrap *group* in a Drawing with white background, export to PNG, save."""
    w, h = canvas
    dwg = svgwrite.Drawing(size=(f"{w}px", f"{h}px"))
    dwg.add(dwg.rect(insert=(0, 0), size=(f"{w}px", f"{h}px"), fill="white"))
    dwg.add(group)
    svg_bytes = dwg.tostring().encode("utf-8")
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes)
    out = FIGURES_DIR / filename
    FIGURES_DIR.mkdir(exist_ok=True)
    out.write_bytes(png_bytes)
    return out


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
    dna_segment((20.0, 100.0), (380.0, 100.0), style=override)
    rna_segment((20.0, 100.0), (380.0, 100.0), style=override)
    chromatin(((20.0, 100.0), (380.0, 100.0)), style=override)


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


def test_nucleic_acids_render_to_png():
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
        out = _render_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"
