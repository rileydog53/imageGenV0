"""Phase 2 Step 6 tests for primitives/chemistry.py.

Tests cover:
- DEFAULT_STYLE completeness (all namespaced keys present)
- Each public function returns Group under its supported parameters
- Invalid SMILES, invalid style name, unknown functional group all raise ValueError
- Style override and palette override actually flow through to the SVG output
- Overlay composability: transparent background + integration with proteins.receptor()
- Render-to-PNG: golden-image seeds for Phase 6 land in tests/figures/
"""
from __future__ import annotations

from pathlib import Path

import cairosvg
import pytest
import svgwrite
import svgwrite.container
from PIL import Image

from imageGen.primitives.chemistry import (
    DEFAULT_STYLE,
    _FUNCTIONAL_GROUPS,
    _reversible_arrow,
    render_functional_group,
    render_molecule,
    render_reaction,
)
from imageGen.primitives.proteins import receptor
from tests._helpers import render_group_to_png

FIGURES_DIR = Path(__file__).parent / "figures"
CAFFEINE = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"


# ---------------------------------------------------------------------------
# DEFAULT_STYLE completeness
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    required = {
        "chem_atom_C", "chem_atom_N", "chem_atom_O", "chem_atom_P", "chem_atom_S",
        "chem_atom_font_scale",
        "chem_bond_stroke", "chem_bond_stroke_width",
        "chem_reaction_arrow_length", "chem_reaction_arrow_stroke",
        "chem_reaction_arrow_stroke_width", "chem_reaction_arrow_head_size",
        "chem_reaction_gap",
        "chem_reaction_plus_font_size", "chem_reaction_plus_color",
        "chem_conditions_font_size", "chem_conditions_color", "chem_conditions_offset",
        "chem_fg_label_font_size", "chem_fg_label_color", "chem_fg_label_offset",
        "label_font_family", "label_font_size", "label_font_color",
    }
    assert required <= set(DEFAULT_STYLE.keys())


# ---------------------------------------------------------------------------
# render_molecule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("style_name", ["skeletal", "ball_stick"])
def test_render_molecule_returns_group(style_name):
    g = render_molecule(CAFFEINE, style=style_name)
    assert isinstance(g, svgwrite.container.Group)


def test_render_molecule_invalid_smiles_raises():
    with pytest.raises(ValueError, match="Invalid SMILES"):
        render_molecule("not-a-smiles!!!")


def test_render_molecule_invalid_style_raises():
    with pytest.raises(ValueError, match="Unknown style"):
        render_molecule(CAFFEINE, style="invalid")


def test_render_molecule_center_translates_group():
    g = render_molecule("CCO", size=(100, 80), center=(200.0, 150.0))
    dwg = svgwrite.Drawing(size=("400px", "300px"))
    dwg.add(g)
    s = dwg.tostring()
    # bbox center (200,150) → translate top-left by (200-50, 150-40) = (150, 110)
    assert "translate(150.0,110.0)" in s


# ---------------------------------------------------------------------------
# render_reaction
# ---------------------------------------------------------------------------

def test_render_reaction_returns_group():
    g = render_reaction(
        ["CC(=O)O", "OCC"],
        ["CC(=O)OCC", "O"],
        conditions={"above": "H+", "below": "Δ"},
    )
    assert isinstance(g, svgwrite.container.Group)


def test_render_reaction_no_conditions():
    g = render_reaction(["C"], ["CO"])
    assert isinstance(g, svgwrite.container.Group)


def test_render_reaction_empty_reactants_raises():
    with pytest.raises(ValueError, match="reactants_smiles"):
        render_reaction([], ["CO"])


def test_render_reaction_empty_products_raises():
    with pytest.raises(ValueError, match="products_smiles"):
        render_reaction(["C"], [])


# ---------------------------------------------------------------------------
# render_functional_group
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(_FUNCTIONAL_GROUPS))
def test_render_functional_group_each_name(name):
    g = render_functional_group(name)
    assert isinstance(g, svgwrite.container.Group)


def test_render_functional_group_unknown_raises():
    with pytest.raises(ValueError, match="Unknown functional group"):
        render_functional_group("not-a-group")


# ---------------------------------------------------------------------------
# Style override flows through to SVG output
# ---------------------------------------------------------------------------

def test_style_override_does_not_crash():
    overrides = {"chem_bond_stroke": "#FF0000", "chem_bond_stroke_width": 4.0,
                 "chem_atom_O": "#00FF00"}
    render_molecule(CAFFEINE, style_dict=overrides)
    render_reaction(["C"], ["CO"], style_dict=overrides)
    render_functional_group("carboxyl", style_dict=overrides)


def test_palette_override_changes_svg_output():
    """Different chem_bond_stroke values must produce different SVG strings."""
    g1 = render_molecule(CAFFEINE, style_dict={"chem_bond_stroke": "#111111"})
    g2 = render_molecule(CAFFEINE, style_dict={"chem_bond_stroke": "#FF00FF"})
    dwg1 = svgwrite.Drawing(size=("300px", "200px")); dwg1.add(g1)
    dwg2 = svgwrite.Drawing(size=("300px", "200px")); dwg2.add(g2)
    s1, s2 = dwg1.tostring(), dwg2.tostring()
    assert s1 != s2
    assert "stroke:#FF00FF" in s2 or "stroke:#ff00ff" in s2.lower()


# ---------------------------------------------------------------------------
# Overlay composability
# ---------------------------------------------------------------------------

def test_chemistry_overlay_is_transparent():
    """Render a molecule on top of a colored rect; verify rect color survives at
    pixels outside the molecule's atoms (proves transparent background)."""
    g = render_molecule("CCO", size=(80, 60), center=(100.0, 100.0))
    dwg = svgwrite.Drawing(size=("200px", "200px"))
    dwg.add(dwg.rect(insert=(0, 0), size=("200px", "200px"), fill="#3366FF"))
    dwg.add(g)
    png_bytes = cairosvg.svg2png(bytestring=dwg.tostring().encode("utf-8"))
    FIGURES_DIR.mkdir(exist_ok=True)
    out = FIGURES_DIR / "chemistry_overlay_transparent.png"
    out.write_bytes(png_bytes)
    img = Image.open(out).convert("RGB")
    # Sample a corner pixel -- must still be the rect's blue, not a white/opaque
    # background painted by the molecule SVG.
    assert img.getpixel((5, 5)) == (51, 102, 255)


def test_molecule_overlays_receptor():
    """Integration: ligand rendered on top of a receptor's binding pocket.
    Eyeball criterion: open the PNG and verify both the receptor and the
    molecule are visible (molecule is on top, receptor not occluded)."""
    receptor_g = receptor(label="EGFR", position=(200.0, 150.0))
    # Binding pocket sits at the extracellular (top) end of the receptor body
    # (lower y in SVG). The receptor body height is 60 by default, so the top
    # is at position.y - 30 = 120.
    ligand_g = render_molecule(CAFFEINE, size=(80, 60), center=(200.0, 100.0))
    dwg = svgwrite.Drawing(size=("400px", "300px"))
    dwg.add(dwg.rect(insert=(0, 0), size=("400px", "300px"), fill="white"))
    dwg.add(receptor_g)
    dwg.add(ligand_g)
    png_bytes = cairosvg.svg2png(bytestring=dwg.tostring().encode("utf-8"))
    FIGURES_DIR.mkdir(exist_ok=True)
    out = FIGURES_DIR / "chemistry_ligand_on_receptor.png"
    out.write_bytes(png_bytes)
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# Render-to-PNG fixtures (Phase 6 golden-image seeds)
# ---------------------------------------------------------------------------

def test_chemistry_renders_to_png():
    render_group_to_png(render_molecule(CAFFEINE), "chemistry_caffeine.png",
                   canvas=(220, 170))
    render_group_to_png(
        render_reaction(["CC(=O)O", "OCC"], ["CC(=O)OCC", "O"],
                        conditions={"above": "H+", "below": "Δ"}),
        "chemistry_reaction_esterification.png",
        canvas=(800, 200),
    )
    for name in ("carboxyl", "amine", "phosphate"):
        render_group_to_png(render_functional_group(name),
                       f"chemistry_fg_{name}.png", canvas=(200, 180))


# ---------------------------------------------------------------------------
# V2 / R2: reversible arrow
# ---------------------------------------------------------------------------

def test_reversible_arrow_returns_four_elements():
    """_reversible_arrow returns two _arrow results (2 elements each) = 4 total."""
    style = {**DEFAULT_STYLE}
    elems = _reversible_arrow((0.0, 50.0), (100.0, 50.0), style)
    assert len(elems) == 4  # forward line + head, backward line + head


def test_reversible_arrow_elements_are_svg():
    """All elements returned by _reversible_arrow must be svgwrite-renderable."""
    style = {**DEFAULT_STYLE}
    for elem in _reversible_arrow((0.0, 0.0), (80.0, 0.0), style):
        assert hasattr(elem, "tostring")


def test_render_reaction_reversible_flag_returns_group():
    """render_reaction(reversible=True) must not raise and must return a Group."""
    g = render_reaction(["CC(=O)O"], ["CCO"], reversible=True)
    assert isinstance(g, svgwrite.container.Group)


def test_render_reaction_reversible_changes_output():
    """SVG output must differ between reversible=True and False (extra arrow elements)."""
    base = render_reaction(["CC"], ["CCO"]).tostring()
    rev = render_reaction(["CC"], ["CCO"], reversible=True).tostring()
    assert base != rev


def test_reversible_gap_style_key_in_default_style():
    """chem_reaction_reversible_gap must be present in DEFAULT_STYLE (V2/R2)."""
    assert "chem_reaction_reversible_gap" in DEFAULT_STYLE


# ---------------------------------------------------------------------------
# V2 / R1: stacked layout
# ---------------------------------------------------------------------------

def test_render_reaction_stack_returns_group():
    """render_reaction(stack=True) must return a Group without raising."""
    g = render_reaction(["CC(=O)O"], ["CCO"], stack=True)
    assert isinstance(g, svgwrite.container.Group)


def test_render_reaction_stack_changes_output():
    """Stacked layout must differ from flat layout in SVG output."""
    flat = render_reaction(["CC(=O)O"], ["CCO"]).tostring()
    stacked = render_reaction(["CC(=O)O"], ["CCO"], stack=True).tostring()
    assert flat != stacked


def test_render_reaction_stack_with_conditions():
    """Stacked layout + conditions must not raise (conditions render in row 2)."""
    g = render_reaction(
        ["CC(=O)O", "CCO"],
        ["CCOC(C)=O"],
        conditions={"above": "H2SO4", "below": "reflux"},
        stack=True,
    )
    assert isinstance(g, svgwrite.container.Group)
    assert g.tostring()  # non-empty SVG


def test_render_reaction_stack_and_reversible_together():
    """stack=True and reversible=True must compose without raising."""
    g = render_reaction(["CC"], ["CCO"], reversible=True, stack=True)
    assert isinstance(g, svgwrite.container.Group)


def test_render_reaction_stacked_to_png():
    """Visual golden seed for the stacked layout."""
    g = render_reaction(
        ["CC(=O)O", "CCO", "c1ccccc1"],
        ["CCOC(C)=O", "O"],
        conditions={"above": "H2SO4 (cat.)", "below": "80°C"},
        stack=True,
    )
    out = render_group_to_png(g, "chemistry_reaction_stacked.png", canvas=(600, 320))
    assert out.exists() and out.stat().st_size > 0


def test_render_reaction_reversible_to_png():
    """Visual golden seed for the reversible arrow."""
    g = render_reaction(
        ["CC(=O)O"],
        ["CCO"],
        conditions={"above": "ΔG"},
        reversible=True,
    )
    out = render_group_to_png(g, "chemistry_reaction_reversible.png", canvas=(600, 180))
    assert out.exists() and out.stat().st_size > 0
