"""Tests for render/compositor.py — Phase 5 Steps 1–2.

Covers: render_figure return value, SVG file validity, style resolution,
format inference/rejection, archetype dispatch (PATHWAY + REACTION_SCHEME),
IR-id tagging (D1), label auto-invoke (D3), watermark stub (D2), and
golden-SVG structure checks for mapk_cascade and oxidation_reaction.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ir.schema import Archetype, Figure
from render.compositor import (
    _needs_watermark,
    _resolve_format,
    _resolve_style,
    _scoped_id,
    render_figure,
)
from tests._helpers import load_fixture

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MAPK = "mapk_cascade.json"
TRANSLOCATION = "multi_compartment_translocation.json"
OXIDATION = "oxidation_reaction.json"
WORKFLOW_FIXTURE = "three_panel_workflow.json"

# Ethanol -> Acetaldehyde for the oxidation_reaction fixture.
OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


# ---------------------------------------------------------------------------
# Return value and file output
# ---------------------------------------------------------------------------


def test_render_figure_returns_path(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    assert isinstance(out, Path)


def test_output_file_exists(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    assert out.exists()


def test_output_is_valid_xml(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    ET.parse(str(out))  # raises if not valid XML


def test_output_root_is_svg(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    tree = ET.parse(str(out))
    root = tree.getroot()
    assert root.tag.endswith("svg")


# ---------------------------------------------------------------------------
# Style resolution
# ---------------------------------------------------------------------------


def test_style_kwarg_overrides_ir_preset(tmp_path):
    ir = load_fixture(MAPK)
    # Should not raise even when style_name differs from any ir.style_preset
    out = render_figure(ir, tmp_path / "fig.svg", style_name="nature")
    assert out.exists()


def test_style_falls_back_to_cell_press_when_neither_set(tmp_path):
    # _resolve_style with no kwarg and no ir.style_preset should use DEFAULT_PRESET
    from ir.schema import Figure, Archetype
    from render.compositor import _resolve_style
    from styles.loader import DEFAULT_PRESET, load_style
    ir = load_fixture(MAPK)
    ir_no_preset = ir.model_copy(update={"style_preset": None})
    assert ir_no_preset.style_preset is None
    d = _resolve_style(ir_no_preset, None)
    assert d == load_style(DEFAULT_PRESET)


def test_resolve_style_prefers_kwarg_over_ir():
    ir = load_fixture(MAPK)
    d = _resolve_style(ir, "nature")
    from styles.loader import load_style
    assert d == load_style("nature")


def test_resolve_style_falls_back_to_default():
    ir = load_fixture(MAPK)
    from styles.loader import DEFAULT_PRESET, load_style
    d = _resolve_style(ir, None)
    assert d == load_style(DEFAULT_PRESET)


# ---------------------------------------------------------------------------
# Format resolution
# ---------------------------------------------------------------------------


def test_format_inferred_from_svg_suffix(tmp_path):
    assert _resolve_format(tmp_path / "x.svg", None) == "svg"


def test_unknown_suffix_raises_value_error(tmp_path):
    with pytest.raises(ValueError, match="Cannot infer"):
        _resolve_format(tmp_path / "x.tiff", None)


def test_explicit_svg_format_accepted(tmp_path):
    assert _resolve_format(tmp_path / "x.svg", "svg") == "svg"


def test_explicit_png_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError, match="png"):
        _resolve_format(tmp_path / "x.png", "png")


def test_explicit_pdf_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError, match="pdf"):
        _resolve_format(tmp_path / "x.pdf", "pdf")


# ---------------------------------------------------------------------------
# Archetype dispatch
# ---------------------------------------------------------------------------


def test_unwired_archetype_raises_not_implemented(tmp_path):
    ir = load_fixture(WORKFLOW_FIXTURE)
    assert ir.archetype == Archetype.WORKFLOW
    with pytest.raises(NotImplementedError, match="WORKFLOW|workflow"):
        render_figure(ir, tmp_path / "fig.svg")


def test_pathway_archetype_does_not_raise(tmp_path):
    ir = load_fixture(MAPK)
    render_figure(ir, tmp_path / "fig.svg")  # no exception


def test_pathway_archetype_ignores_smiles_map(tmp_path):
    """Regression: smiles_map=None on a PATHWAY must not raise (smiles_map
    is REACTION_SCHEME-only)."""
    ir = load_fixture(MAPK)
    render_figure(ir, tmp_path / "fig.svg", smiles_map=None)  # no exception


# ---------------------------------------------------------------------------
# REACTION_SCHEME dispatch (Step 2)
# ---------------------------------------------------------------------------


def test_reaction_scheme_renders_with_smiles_map(tmp_path):
    ir = load_fixture(OXIDATION)
    out = render_figure(ir, tmp_path / "fig.svg", smiles_map=OXIDATION_SMILES)
    assert out.exists()


def test_reaction_scheme_output_is_valid_xml(tmp_path):
    ir = load_fixture(OXIDATION)
    out = render_figure(ir, tmp_path / "fig.svg", smiles_map=OXIDATION_SMILES)
    ET.parse(str(out))  # raises if not valid XML


def test_reaction_scheme_missing_smiles_map_raises(tmp_path):
    """ValueError must list every entity id when smiles_map is None."""
    ir = load_fixture(OXIDATION)
    with pytest.raises(ValueError, match="smiles_map required for REACTION_SCHEME") as exc:
        render_figure(ir, tmp_path / "fig.svg")  # smiles_map omitted
    for eid in ("alcohol", "aldehyde"):
        assert eid in str(exc.value), f"entity id {eid!r} not in error message"


def test_reaction_scheme_tagged_with_data_ir_id(tmp_path):
    """D1: the reaction_0 entry's group must carry data-ir-id.

    Guards the debug=False path in _tag_group / _write_svg — svgwrite's
    strict validator rejects data-* attrs by default.
    """
    ir = load_fixture(OXIDATION)
    out = render_figure(ir, tmp_path / "fig.svg", smiles_map=OXIDATION_SMILES)
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    assert "reaction_0" in tagged


def test_reaction_scheme_style_kwarg_accepted(tmp_path):
    ir = load_fixture(OXIDATION)
    out = render_figure(
        ir, tmp_path / "fig.svg", style_name="nature", smiles_map=OXIDATION_SMILES
    )
    assert out.exists()


def test_golden_svg_oxidation_reaction(tmp_path):
    """Render oxidation_reaction and verify the reaction_0 group is tagged."""
    ir = load_fixture(OXIDATION)
    out = render_figure(
        ir, tmp_path / "oxidation_reaction.svg", smiles_map=OXIDATION_SMILES
    )

    tagged = _svg_elements_with_attr(out, "data-ir-id")
    assert "reaction_0" in tagged

    # Produce a fixture PNG for visual inspection (mirrors mapk_cascade).
    from tests._helpers import FIGURES_DIR
    import cairosvg
    FIGURES_DIR.mkdir(exist_ok=True)
    png_path = FIGURES_DIR / "compositor_oxidation_reaction.png"
    png_path.write_bytes(cairosvg.svg2png(url=str(out)))
    assert png_path.exists()


# ---------------------------------------------------------------------------
# IR-id tagging (D1)
# ---------------------------------------------------------------------------


def _svg_elements_with_attr(svg_path: Path, attr: str) -> list[str]:
    """Return all values of `attr` found on any element in the SVG."""
    tree = ET.parse(str(svg_path))
    return [el.get(attr) for el in tree.iter() if el.get(attr) is not None]


def test_entity_ids_tagged_as_data_ir_id(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    entity_ids = {e.id for e in ir.entities}
    for eid in entity_ids:
        assert eid in tagged, f"entity id {eid!r} not found in data-ir-id attrs"


def test_compartment_ids_tagged_as_data_ir_id(tmp_path):
    ir = load_fixture(TRANSLOCATION)
    assert ir.compartments, "fixture must have compartments"
    out = render_figure(ir, tmp_path / "fig.svg")
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    for c in ir.compartments:
        assert c.id in tagged, f"compartment id {c.id!r} not found in data-ir-id attrs"


def test_relation_synthetic_ids_tagged(tmp_path):
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    for r in ir.relations:
        expected = f"rel_{r.source}_{r.type.value}_{r.target}"
        assert expected in tagged, f"relation id {expected!r} not found in data-ir-id attrs"


def test_scoped_id_at_depth_zero_equals_raw_id():
    assert _scoped_id("ras", ()) == "ras"


def test_scoped_id_with_panel_chain():
    assert _scoped_id("ras", ("panel_a",)) == "panel_a__ras"
    assert _scoped_id("ras", ("panel_a", "panel_b")) == "panel_a__panel_b__ras"


def test_svg_id_equals_data_ir_id_at_depth_zero(tmp_path):
    """At depth 0 (no panel nesting) the SVG id and data-ir-id must match."""
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.svg")
    tree = ET.parse(str(out))
    for el in tree.iter():
        if el.get("data-ir-id") is not None:
            assert el.get("id") == el.get("data-ir-id"), (
                f"id {el.get('id')!r} != data-ir-id {el.get('data-ir-id')!r}"
            )


# ---------------------------------------------------------------------------
# Label auto-invoke (D3)
# ---------------------------------------------------------------------------


def test_labels_true_produces_label_elements(tmp_path):
    ir = load_fixture(TRANSLOCATION)
    labeled_rels = [r for r in ir.relations if r.label]
    assert labeled_rels, "fixture must have labeled relations"
    out = render_figure(ir, tmp_path / "fig.svg", labels=True)
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    label_tags = [t for t in tagged if t.startswith("label_")]
    assert label_tags, "expected label_ data-ir-id entries with labels=True"


def test_labels_false_suppresses_label_elements(tmp_path):
    ir = load_fixture(TRANSLOCATION)
    out = render_figure(ir, tmp_path / "fig.svg", labels=False)
    tagged = _svg_elements_with_attr(out, "data-ir-id")
    label_tags = [t for t in tagged if t.startswith("label_")]
    assert not label_tags, "expected no label_ data-ir-id entries with labels=False"


# ---------------------------------------------------------------------------
# Watermark stub (D2)
# ---------------------------------------------------------------------------


def test_needs_watermark_returns_false_for_pathway():
    ir = load_fixture(MAPK)
    assert _needs_watermark(ir) is False


def test_needs_watermark_returns_false_for_all_fixtures():
    fixtures = [
        "mapk_cascade.json", "simple_activation.json",
        "gpcr_signaling.json", "multi_compartment_translocation.json",
    ]
    for name in fixtures:
        ir = load_fixture(name)
        assert _needs_watermark(ir) is False, f"unexpected True for {name}"


# ---------------------------------------------------------------------------
# Golden SVG — structure check (not pixel-level)
# ---------------------------------------------------------------------------


def test_golden_svg_mapk_cascade(tmp_path):
    """Render mapk_cascade and verify structure: all 4 entities + 3 relations tagged."""
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "mapk_cascade.svg")

    tagged = _svg_elements_with_attr(out, "data-ir-id")
    # 4 entities
    for eid in ("ras", "raf", "mek", "erk"):
        assert eid in tagged
    # 3 relations
    assert "rel_ras_activates_raf" in tagged
    assert "rel_raf_phosphorylates_mek" in tagged
    assert "rel_mek_phosphorylates_erk" in tagged

    # Produce a fixture PNG for visual inspection
    from tests._helpers import FIGURES_DIR
    import cairosvg
    FIGURES_DIR.mkdir(exist_ok=True)
    png_path = FIGURES_DIR / "compositor_mapk_cascade.png"
    png_path.write_bytes(cairosvg.svg2png(url=str(out)))
    assert png_path.exists()
