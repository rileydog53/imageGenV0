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
from PIL import Image

from imageGenV0.ir.schema import Archetype, Figure
from imageGenV0.render.compositor import (
    _needs_watermark,
    _resolve_format,
    _resolve_style,
    render_figure,
    scoped_id,
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
    from imageGenV0.ir.schema import Figure, Archetype
    from imageGenV0.render.compositor import _resolve_style
    from imageGenV0.styles.loader import DEFAULT_PRESET, load_style
    ir = load_fixture(MAPK)
    ir_no_preset = ir.model_copy(update={"style_preset": None})
    assert ir_no_preset.style_preset is None
    d = _resolve_style(ir_no_preset, None)
    assert d == load_style(DEFAULT_PRESET)


def test_resolve_style_prefers_kwarg_over_ir():
    ir = load_fixture(MAPK)
    d = _resolve_style(ir, "nature")
    from imageGenV0.styles.loader import load_style
    assert d == load_style("nature")


def test_resolve_style_falls_back_to_default():
    ir = load_fixture(MAPK)
    from imageGenV0.styles.loader import DEFAULT_PRESET, load_style
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


def test_explicit_png_format_accepted(tmp_path):
    assert _resolve_format(tmp_path / "x.png", "png") == "png"


def test_explicit_pdf_format_accepted(tmp_path):
    assert _resolve_format(tmp_path / "x.pdf", "pdf") == "pdf"


# ---------------------------------------------------------------------------
# Non-SVG output (Step 4: PNG + PDF via render/export.py)
# ---------------------------------------------------------------------------


def test_render_figure_png_end_to_end(tmp_path):
    """`format='png'` writes a Pillow-readable PNG plus a sibling SVG."""
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.png")
    assert out == tmp_path / "fig.png"
    assert out.exists()
    assert (tmp_path / "fig.svg").exists(), "sibling SVG should be persisted"
    with Image.open(out) as img:
        assert img.format == "PNG"


def test_render_figure_pdf_end_to_end(tmp_path):
    """`format='pdf'` writes a real PDF plus a sibling SVG."""
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.pdf")
    assert out == tmp_path / "fig.pdf"
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
    assert (tmp_path / "fig.svg").exists(), "sibling SVG should be persisted"


def test_render_figure_png_forwards_dpi(tmp_path):
    """Higher `dpi` yields a larger PNG — proves the kwarg threads through."""
    ir = load_fixture(MAPK)
    lo = render_figure(ir, tmp_path / "lo.png", dpi=96)
    hi = render_figure(ir, tmp_path / "hi.png", dpi=300)
    with Image.open(lo) as a, Image.open(hi) as b:
        assert b.width > a.width


def test_render_figure_format_kwarg_overrides_suffix(tmp_path):
    """Explicit `format='png'` on a non-png suffix still produces a PNG."""
    ir = load_fixture(MAPK)
    out = render_figure(ir, tmp_path / "fig.out", format="png")
    assert out.exists()
    with Image.open(out) as img:
        assert img.format == "PNG"


# ---------------------------------------------------------------------------
# Archetype dispatch
# ---------------------------------------------------------------------------


def test_unwired_leaf_archetype_raises_not_implemented(tmp_path):
    """Leaf WORKFLOW (no panels) is still unwired at the compositor level.

    Repurposed from the Step 2 fixture-based version: three_panel_workflow
    now dispatches successfully through layout_panel, so the unwired path
    is exercised here with an inline panel-less WORKFLOW figure.
    """
    ir = Figure(
        archetype=Archetype.WORKFLOW,
        entities=[{"id": "a", "type": "sample", "label": "A"}],
        relations=[],
    )
    assert not ir.panels
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
        assert r.ir_id in tagged, f"relation id {r.ir_id!r} not found in data-ir-id attrs"


def test_scoped_id_at_depth_zero_equals_raw_id():
    assert scoped_id("ras", ()) == "ras"


def test_scoped_id_with_panel_chain():
    assert scoped_id("ras", ("panel_a",)) == "panel_a__ras"
    assert scoped_id("ras", ("panel_a", "panel_b")) == "panel_a__panel_b__ras"


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


# ---------------------------------------------------------------------------
# PANEL dispatch (Step 3)
# ---------------------------------------------------------------------------


def _svg_id_pairs(svg_path: Path) -> list[tuple[str | None, str | None]]:
    """Return (id, data-ir-id) for every element carrying data-ir-id."""
    tree = ET.parse(str(svg_path))
    return [
        (el.get("id"), el.get("data-ir-id"))
        for el in tree.iter()
        if el.get("data-ir-id") is not None
    ]


def test_panel_figure_renders(tmp_path):
    ir = load_fixture(WORKFLOW_FIXTURE)
    assert ir.panels, "fixture must have panels"
    out = render_figure(ir, tmp_path / "fig.svg")
    assert out.exists()


def test_panel_figure_output_is_valid_xml(tmp_path):
    ir = load_fixture(WORKFLOW_FIXTURE)
    out = render_figure(ir, tmp_path / "fig.svg")
    ET.parse(str(out))  # raises if not valid XML


def test_panel_entity_ids_have_scoped_svg_ids(tmp_path):
    """Each entity from each panel.content has id=<panel.id>__<entity.id>
    and data-ir-id=<entity.id> (D1)."""
    ir = load_fixture(WORKFLOW_FIXTURE)
    out = render_figure(ir, tmp_path / "fig.svg")
    pairs = _svg_id_pairs(out)
    by_data: dict[str, set[str | None]] = {}
    for svg_id, data_id in pairs:
        by_data.setdefault(data_id, set()).add(svg_id)

    for panel in ir.panels:
        for entity in panel.content.entities:
            scoped = f"{panel.id}__{entity.id}"
            assert entity.id in by_data, (
                f"data-ir-id {entity.id!r} not found in SVG"
            )
            assert scoped in by_data[entity.id], (
                f"expected svg id {scoped!r} for entity {entity.id!r}, "
                f"got {by_data[entity.id]!r}"
            )


def test_panel_chrome_tagged_with_unprefixed_ids(tmp_path):
    """Chrome entries' ir_id is already panel-scoped (`p1_chrome`);
    panel_chain is empty so SVG id == data-ir-id."""
    ir = load_fixture(WORKFLOW_FIXTURE)
    out = render_figure(ir, tmp_path / "fig.svg")
    pairs = _svg_id_pairs(out)
    for panel in ir.panels:
        chrome_id = f"{panel.id}_chrome"
        match = [(s, d) for s, d in pairs if d == chrome_id]
        assert match, f"chrome data-ir-id {chrome_id!r} not found"
        assert all(s == chrome_id for s, _ in match), (
            f"chrome svg id should equal data-ir-id {chrome_id!r}, "
            f"got {match!r}"
        )


def test_panel_labels_placed_per_panel(tmp_path):
    """Relation labels (e.g. `treat`, `lyse`) render and carry
    panel-scoped svg ids."""
    ir = load_fixture(WORKFLOW_FIXTURE)
    out = render_figure(ir, tmp_path / "fig.svg", labels=True)
    pairs = _svg_id_pairs(out)
    label_pairs = [(s, d) for s, d in pairs if d and d.startswith("label_")]
    assert label_pairs, "expected at least one label_* data-ir-id"
    # At least one label's svg id should be panel-scoped.
    scoped = [
        (s, d) for s, d in label_pairs
        if s and "__" in s and s.split("__", 1)[1] == d
    ]
    assert scoped, (
        f"expected at least one label with panel-scoped svg id, "
        f"got {label_pairs!r}"
    )


def test_panel_figure_with_reaction_inside(tmp_path):
    """Flat smiles_map broadcasts to all panels; one REACTION_SCHEME
    panel renders without error."""
    ir = Figure(
        archetype=Archetype.WORKFLOW,
        title="reaction-in-panel",
        panels=[
            {
                "id": "p1",
                "title": "Step 1",
                "grid": [0, 0, 1, 1],
                "content": {
                    "archetype": "workflow",
                    "entities": [
                        {"id": "cells", "type": "sample", "label": "Cells"},
                        {"id": "drug", "type": "ligand", "label": "Drug"},
                    ],
                    "relations": [
                        {"source": "drug", "target": "cells", "type": "generic"}
                    ],
                },
            },
            {
                "id": "p2",
                "title": "Step 2",
                "grid": [0, 1, 1, 1],
                "content": {
                    "archetype": "reaction_scheme",
                    "entities": [
                        {"id": "alcohol", "type": "metabolite", "label": "EtOH"},
                        {"id": "aldehyde", "type": "metabolite", "label": "AcH"},
                    ],
                    "relations": [
                        {"source": "alcohol", "target": "aldehyde", "type": "generic"}
                    ],
                },
            },
        ],
    )
    smiles_map = {"alcohol": "CCO", "aldehyde": "CC=O"}
    out = render_figure(ir, tmp_path / "fig.svg", smiles_map=smiles_map)
    assert out.exists()
    pairs = _svg_id_pairs(out)
    data_ids = {d for _, d in pairs}
    assert "reaction_0" in data_ids
    assert "cells" in data_ids


def test_panel_figure_missing_smiles_map_raises_for_reaction_panel(tmp_path):
    """Omitting smiles_map when a panel contains a REACTION_SCHEME
    raises ValueError naming the reaction panel id."""
    ir = Figure(
        archetype=Archetype.WORKFLOW,
        panels=[
            {
                "id": "rxn_panel",
                "title": "Rxn",
                "grid": [0, 0, 1, 1],
                "content": {
                    "archetype": "reaction_scheme",
                    "entities": [
                        {"id": "alcohol", "type": "metabolite", "label": "EtOH"},
                        {"id": "aldehyde", "type": "metabolite", "label": "AcH"},
                    ],
                    "relations": [
                        {"source": "alcohol", "target": "aldehyde", "type": "generic"}
                    ],
                },
            },
        ],
    )
    with pytest.raises(ValueError, match="rxn_panel"):
        render_figure(ir, tmp_path / "fig.svg")


def test_golden_svg_three_panel_workflow(tmp_path):
    """End-to-end golden: render three_panel_workflow, verify per-panel
    entity tagging, and emit the PNG for visual review."""
    ir = load_fixture(WORKFLOW_FIXTURE)
    out = render_figure(ir, tmp_path / "three_panel_workflow.svg")
    pairs = _svg_id_pairs(out)
    data_ids = {d for _, d in pairs}

    for panel in ir.panels:
        assert f"{panel.id}_chrome" in data_ids
        for entity in panel.content.entities:
            assert entity.id in data_ids

    from tests._helpers import FIGURES_DIR
    import cairosvg
    FIGURES_DIR.mkdir(exist_ok=True)
    png_path = FIGURES_DIR / "compositor_three_panel_workflow.png"
    png_path.write_bytes(cairosvg.svg2png(url=str(out)))
    assert png_path.exists()
