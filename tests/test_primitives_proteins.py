"""Phase 2 Step 2 tests for primitives/proteins.py.

Each public function gets a type-check test plus state variations (phosphorylated kinase,
DNA-binding TF, rotated receptor). A render test produces fixture PNGs covering every
function and every visual state — these become golden-image seeds for Phase 6.
"""
from __future__ import annotations

import math

import pytest
import svgwrite
import svgwrite.container

from imageGen.primitives.proteins import (
    DEFAULT_STYLE,
    generic_protein,
    gpcr,
    kinase,
    protein_complex,
    receptor,
    transcription_factor,
)
from tests._helpers import render_group_to_png


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


def test_protein_complex_returns_group():
    g = protein_complex("RNP", (100, 70))
    assert isinstance(g, svgwrite.container.Group)


def test_protein_complex_draws_two_subunit_rects_spanning_size():
    """LT6 ext: a complex is two overlapping rects that together span ``size``,
    so its rendered footprint matches ENTITY_BBOX[COMPLEX]."""
    cx, cy, w, h = 100.0, 70.0, 72.0, 38.0
    g = protein_complex("RNP", (cx, cy), size=(w, h))
    rects = [el for el in g.elements if isinstance(el, svgwrite.shapes.Rect)]
    assert len(rects) == 2

    xs0 = [float(r["x"]) for r in rects]
    ys0 = [float(r["y"]) for r in rects]
    xs1 = [float(r["x"]) + float(r["width"]) for r in rects]
    ys1 = [float(r["y"]) + float(r["height"]) for r in rects]
    assert min(xs0) == pytest.approx(cx - w / 2)
    assert max(xs1) == pytest.approx(cx + w / 2)
    assert min(ys0) == pytest.approx(cy - h / 2)
    assert max(ys1) == pytest.approx(cy + h / 2)


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

def test_proteinsrender_group_to_png():
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
        out = render_group_to_png(group, filename, canvas=canvas)
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"


# ---------------------------------------------------------------------------
# Label fitting (LABEL_FIT) — entity labels never overflow their box
# ---------------------------------------------------------------------------

def _text_attr(group: svgwrite.container.Group, attr: str) -> str | None:
    """Return ``attr`` of the first <text> in the group's serialized XML."""
    import re
    xml = group.tostring()
    m = re.search(r"<text\b[^>]*\b" + re.escape(attr) + r'="([^"]*)"', xml)
    return m.group(1) if m else None


def test_short_label_renders_single_base_font_text():
    # A label that fits is byte-for-byte the pre-fit centered label.
    g = generic_protein("ATP", (100, 70))
    xml = g.tostring()
    assert "<tspan" not in xml
    assert _text_attr(g, "font-size") == str(float(DEFAULT_STYLE["label_font_size"]))


def test_long_label_shrinks_to_fit_default_box():
    # "Oxaloacetate" overflows a 60px box at 11px → shrunk single line.
    g = generic_protein("Oxaloacetate", (100, 70), size=(60, 30))
    xml = g.tostring()
    assert "Oxaloacetate" in xml
    assert "<tspan" not in xml
    fs = float(_text_attr(g, "font-size"))
    assert fs < float(DEFAULT_STYLE["label_font_size"])
    assert fs >= 7.0  # the shrink floor, above the legibility minimum


def test_long_hyphenated_label_wraps_to_two_lines():
    g = generic_protein("alpha-Ketoglutarate", (100, 70), size=(60, 30))
    xml = g.tostring()
    assert xml.count("<tspan") == 2


def test_pathological_label_renders_empty_box_for_external_placement():
    # Rung 4: even the floor font overflows → no in-box <text>; the layout
    # engine places the label outside on a leader.
    g = generic_protein("Supercalifragilisticexpialidocious", (100, 70), size=(60, 30))
    xml = g.tostring()
    assert "<text" not in xml and "<tspan" not in xml
    assert "<rect" in xml  # the box itself still renders


def test_kinase_long_label_fits_inside_hexagon():
    g = kinase("Target Kinase", (100, 70), size=(70, 32))
    xml = g.tostring()
    assert "Target Kinase" in xml or xml.count("<tspan") == 2
    # 'P' badge absent (not phosphorylated), so the only text is the label.
    fs = float(_text_attr(g, "font-size"))
    assert fs <= float(DEFAULT_STYLE["label_font_size"])


def test_protein_complex_long_label_fits():
    g = protein_complex("IκB·NF-κB", (100, 70), size=(72, 38))
    xml = g.tostring()
    assert "NF-κB" in xml  # label still present, just fitted
    assert "<text" in xml or "<tspan" in xml
