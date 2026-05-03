"""Phase 2 Step 2 tests for primitives/proteins.py.

Each public function gets a type-check test plus state variations (phosphorylated kinase,
DNA-binding TF, rotated receptor). A render test produces fixture PNGs covering every
function and every visual state — these become golden-image seeds for Phase 6.
"""
from __future__ import annotations

import math
from pathlib import Path

import cairosvg
import svgwrite
import svgwrite.container

from primitives.proteins import (
    DEFAULT_STYLE,
    generic_protein,
    gpcr,
    kinase,
    receptor,
    transcription_factor,
)

FIGURES_DIR = Path(__file__).parent / "figures"


def _render_to_png(
    group: svgwrite.container.Group,
    filename: str,
    canvas: tuple[int, int] = (200, 140),
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
# Type-check tests
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    """DEFAULT_STYLE must define every key each function pulls from."""
    required = {
        "protein_fill", "protein_stroke", "protein_stroke_width", "protein_corner_radius",
        "kinase_fill", "kinase_stroke", "kinase_badge_fill", "kinase_badge_text_color",
        "receptor_fill", "receptor_stroke",
        "gpcr_helix_fill", "gpcr_helix_stroke", "gpcr_loop_stroke", "gpcr_loop_stroke_width",
        "tf_fill", "tf_stroke", "tf_dbd_fill",
        "label_font_family", "label_font_size", "label_font_color",
    }
    missing = required - set(DEFAULT_STYLE.keys())
    assert not missing, f"DEFAULT_STYLE missing keys: {missing}"


def test_generic_protein_returns_group():
    g = generic_protein("EGF", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_kinase_returns_group():
    g = kinase("MEK1", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_kinase_phosphorylated_returns_group():
    g = kinase("ERK", (100, 70), phosphorylated=True)
    assert isinstance(g, svgwrite.container.Group)


def test_receptor_returns_group():
    g = receptor("EGFR", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_receptor_oriented_returns_group():
    """Non-zero orientation should still return a Group (rotation applied via transform)."""
    g = receptor("EGFR", (100, 70), orientation=math.pi / 6)
    assert isinstance(g, svgwrite.container.Group)


def test_gpcr_returns_group():
    g = gpcr("β2AR", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_transcription_factor_returns_group():
    g = transcription_factor("MyoD", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_transcription_factor_dna_binding_returns_group():
    g = transcription_factor("p53", (100, 70), dna_binding=True)
    assert isinstance(g, svgwrite.container.Group)


def test_color_override_does_not_crash():
    """Passing a custom `color` kwarg should swap the fill cleanly for every protein."""
    for fn, args in [
        (generic_protein, ("X", (100, 70))),
        (kinase, ("X", (100, 70))),
        (receptor, ("X", (100, 70))),
        (gpcr, ("X", (100, 70))),
        (transcription_factor, ("X", (100, 70))),
    ]:
        g = fn(*args, color="#FF00AA")
        assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Render-to-PNG test — produces golden-image seeds for Phase 6
# ---------------------------------------------------------------------------

def test_proteins_render_to_png():
    """Render one PNG per protein variant; assert each file exists and is non-empty."""
    cases: dict[str, tuple[svgwrite.container.Group, tuple[int, int]]] = {
        "protein_generic.png": (generic_protein("EGF", (100, 70)), (200, 140)),
        "protein_kinase.png": (kinase("MEK1", (100, 70)), (200, 140)),
        "protein_kinase_phosphorylated.png": (
            kinase("ERK", (100, 70), phosphorylated=True),
            (200, 140),
        ),
        "protein_receptor.png": (receptor("EGFR", (100, 70)), (200, 140)),
        "protein_receptor_rotated.png": (
            receptor("Notch", (100, 70), orientation=math.pi / 6),
            (200, 140),
        ),
        "protein_gpcr.png": (gpcr("β2AR", (110, 60)), (220, 140)),
        "protein_tf.png": (transcription_factor("MyoD", (100, 50)), (200, 140)),
        "protein_tf_dna_binding.png": (
            transcription_factor("p53", (100, 50), dna_binding=True),
            (200, 140),
        ),
    }
    for filename, (group, canvas) in cases.items():
        out = _render_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"
