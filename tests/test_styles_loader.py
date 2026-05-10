"""Phase 4 tests for styles/loader.py."""
from __future__ import annotations

import json
from pathlib import Path

import cairosvg
import pytest
import svgwrite
import svgwrite.container
from pydantic import ValidationError

from ir.schema import Figure
from layout.pathway_layout import layout_pathway
from layout.reaction_layout import LayoutEntry, layout_reaction
from styles.loader import (
    DEFAULT_PRESET,
    PRESET_DIR,
    StylePreset,
    list_presets,
    load_preset_full,
    load_style,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIGURES_DIR = Path(__file__).parent / "figures"

# Map from oxidation_reaction.json entity ids → SMILES (kept here, not
# in the IR; matches the smiles_map convention from layout_reaction).
_OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


def _load_fixture(name: str) -> Figure:
    return Figure.model_validate(json.loads((FIXTURES_DIR / name).read_text()))


def _render_to_png(
    entries: list[LayoutEntry],
    filename: str,
    canvas: tuple[int, int] = (800, 600),
) -> Path:
    w, h = canvas
    dwg = svgwrite.Drawing(size=(f"{w}px", f"{h}px"))
    dwg.add(dwg.rect(insert=(0, 0), size=(f"{w}px", f"{h}px"), fill="white"))
    for e in entries:
        g = e.primitive(*e.args, **e.kwargs)
        px, py = e.position
        if (px, py) != (0.0, 0.0):
            wrap = svgwrite.container.Group(transform=f"translate({px},{py})")
            wrap.add(g)
            dwg.add(wrap)
        else:
            dwg.add(g)
    FIGURES_DIR.mkdir(exist_ok=True)
    out = FIGURES_DIR / filename
    out.write_bytes(cairosvg.svg2png(bytestring=dwg.tostring().encode("utf-8")))
    return out


# ---------------------------------------------------------------------------
# Loader: shape + defaults
# ---------------------------------------------------------------------------

def test_load_style_returns_dict():
    style = load_style()
    assert isinstance(style, dict)
    assert style  # non-empty (cell_press has 15 overrides)


def test_load_style_default_is_cell_press():
    assert load_style() == load_style("cell_press")
    assert DEFAULT_PRESET == "cell_press"


def test_load_style_unknown_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="vogue"):
        load_style("vogue")


def test_list_presets_finds_three():
    presets = list_presets()
    assert set(presets) == {"cell_press", "nature", "acs"}
    assert presets == sorted(presets)


# ---------------------------------------------------------------------------
# Preset content validation (each shipped preset)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["cell_press", "nature", "acs"])
def test_preset_palette_length(name):
    p = load_preset_full(name)
    assert len(p.palette) == 8


@pytest.mark.parametrize("name", ["cell_press", "nature", "acs"])
def test_preset_palette_hex_format(name):
    p = load_preset_full(name)
    for c in p.palette:
        assert isinstance(c, str)
        assert len(c) == 7 and c.startswith("#")
        int(c[1:], 16)  # parses as hex


@pytest.mark.parametrize("name", ["cell_press", "nature", "acs"])
def test_preset_meta_present(name):
    p = load_preset_full(name)
    assert p.meta.name == name
    assert p.meta.description.strip()


# ---------------------------------------------------------------------------
# Schema enforcement (negative cases)
# ---------------------------------------------------------------------------

def test_load_style_invalid_palette_length_raises(tmp_path, monkeypatch):
    """A preset with the wrong palette length must fail validation."""
    bad = tmp_path / "broken.json"
    bad.write_text(json.dumps({
        "meta": {"name": "broken", "description": "x"},
        "palette": ["#000000", "#FFFFFF"],  # only 2
        "overrides": {},
    }))
    monkeypatch.setattr("styles.loader.PRESET_DIR", tmp_path)
    with pytest.raises(ValidationError, match="palette"):
        load_preset_full("broken")


def test_load_style_invalid_hex_raises(tmp_path, monkeypatch):
    bad = tmp_path / "broken.json"
    bad.write_text(json.dumps({
        "meta": {"name": "broken", "description": "x"},
        "palette": ["red"] * 8,  # not hex
        "overrides": {},
    }))
    monkeypatch.setattr("styles.loader.PRESET_DIR", tmp_path)
    with pytest.raises(ValidationError, match="hex"):
        load_preset_full("broken")


def test_load_style_unknown_extra_field_raises(tmp_path, monkeypatch):
    """`extra="forbid"` must reject unknown top-level fields (typo guard)."""
    bad = tmp_path / "broken.json"
    bad.write_text(json.dumps({
        "meta": {"name": "broken", "description": "x"},
        "palette": ["#" + "0" * 6] * 8,
        "overrides": {},
        "stray_field": "uh oh",
    }))
    monkeypatch.setattr("styles.loader.PRESET_DIR", tmp_path)
    with pytest.raises(ValidationError):
        load_preset_full("broken")


# ---------------------------------------------------------------------------
# Overrides plumb through to primitives
# ---------------------------------------------------------------------------

def test_overrides_plumb_to_primitive_render():
    """Loading nature should change the SVG fill on a generic_protein."""
    from primitives import proteins

    style = load_style("nature")
    g = proteins.generic_protein("X", (50, 50), style_dict=style)
    svg_str = g.tostring()
    assert style["protein_fill"] in svg_str


def test_overrides_dont_break_primitives_with_missing_keys():
    """A sparse preset (missing most primitive keys) must still render
    every primitive — primitive DEFAULT_STYLE fills the gaps."""
    from primitives import arrows, membranes, proteins
    style = load_style("cell_press")  # has only ~15 keys

    # Each call must succeed without KeyError (primitives merge with their
    # own DEFAULT_STYLE under the hood).
    proteins.kinase("K", (100, 100), style_dict=style)
    proteins.gpcr("G", (100, 100), style_dict=style)
    arrows.activation_arrow((10, 10), (50, 50), style_dict=style)
    membranes.cell_membrane_outline(shape="circle", size=(80, 80), style_dict=style)


def test_acs_has_monochrome_protein_fills():
    """ACS strips color from proteins — fills should all be near-greyscale."""
    p = load_preset_full("acs")
    color_keys = ("protein_fill", "kinase_fill", "receptor_fill", "tf_fill")
    for k in color_keys:
        if k not in p.overrides:
            continue
        c = p.overrides[k].lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        # Greyscale = R == G == B (ACS uses pure grey for all non-chemistry fills).
        assert r == g == b, f"{k} = {p.overrides[k]} is not pure grey"


# ---------------------------------------------------------------------------
# Render-to-PNG goldens (3 presets × 2 fixtures = 6 files)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", ["cell_press", "nature", "acs"])
def test_render_mapk_with_preset(preset):
    fig = _load_fixture("mapk_cascade.json")
    style = load_style(preset)
    entries = layout_pathway(fig, style_dict=style)
    out = _render_to_png(entries, f"style_{preset}_mapk.png")
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.parametrize("preset", ["cell_press", "nature", "acs"])
def test_render_oxidation_with_preset(preset):
    fig = _load_fixture("oxidation_reaction.json")
    style = load_style(preset)
    entries = layout_reaction(fig, smiles_map=_OXIDATION_SMILES, style_dict=style)
    out = _render_to_png(entries, f"style_{preset}_oxidation.png")
    assert out.exists() and out.stat().st_size > 0
