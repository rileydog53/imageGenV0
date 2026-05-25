"""Phase 4 tests for styles/loader.py."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from imageGen.ir.schema import Figure
from imageGen.layout.pathway_layout import layout_pathway
from imageGen.layout.reaction_layout import layout_reaction
from imageGen.layout.types import LayoutEntry
from imageGen.styles.loader import (
    DEFAULT_PRESET,
    KNOWN_LAYOUT_PARAMS,
    KNOWN_STYLE_KEYS,
    PRESET_DIR,
    StylePreset,
    list_presets,
    load_layout_params,
    load_preset_full,
    load_style,
)
from tests._helpers import load_fixture, render_entries_to_png

# Map from oxidation_reaction.json entity ids → SMILES (kept here, not
# in the IR; matches the smiles_map convention from layout_reaction).
_OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


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
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
    with pytest.raises(ValidationError, match="palette"):
        load_preset_full("broken")


def test_load_style_invalid_hex_raises(tmp_path, monkeypatch):
    bad = tmp_path / "broken.json"
    bad.write_text(json.dumps({
        "meta": {"name": "broken", "description": "x"},
        "palette": ["red"] * 8,  # not hex
        "overrides": {},
    }))
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
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
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
    with pytest.raises(ValidationError):
        load_preset_full("broken")


# ---------------------------------------------------------------------------
# Overrides plumb through to primitives
# ---------------------------------------------------------------------------

def test_overrides_plumb_to_primitive_render():
    """Loading nature should change the SVG fill on a generic_protein."""
    from imageGen.primitives import proteins

    style = load_style("nature")
    g = proteins.generic_protein("X", (50, 50), style_dict=style)
    svg_str = g.tostring()
    assert style["protein_fill"] in svg_str


def test_overrides_dont_break_primitives_with_missing_keys():
    """A sparse preset (missing most primitive keys) must still render
    every primitive — primitive DEFAULT_STYLE fills the gaps."""
    from imageGen.primitives import arrows, membranes, proteins
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
# V2 / ST2: KNOWN_LAYOUT_PARAMS and load_layout_params
# ---------------------------------------------------------------------------

def test_known_layout_params_is_nonempty_frozenset():
    """KNOWN_LAYOUT_PARAMS must be a non-empty frozenset (ST2 guard is live)."""
    assert isinstance(KNOWN_LAYOUT_PARAMS, frozenset)
    assert len(KNOWN_LAYOUT_PARAMS) > 0


def test_known_layout_params_contains_key_aesthetic_params():
    """Spot-check: representative aesthetic keys from each layout engine."""
    expected = {
        "pathway_band_fill", "pathway_band_stroke", "pathway_band_stroke_width",
        "pathway_band_label_color", "pathway_band_label_size", "pathway_band_label_family",
        "panel_border_stroke", "panel_border_stroke_width", "panel_border_fill",
        "panel_title_color", "panel_title_size", "panel_title_family", "panel_title_weight",
    }
    missing = expected - KNOWN_LAYOUT_PARAMS
    assert not missing, f"Keys missing from KNOWN_LAYOUT_PARAMS: {sorted(missing)}"


def test_known_layout_params_excludes_geometric_knobs():
    """Geometric / behavioral params must NOT appear in KNOWN_LAYOUT_PARAMS."""
    geometric = {
        "pathway_canvas", "pathway_origin", "pathway_seed",
        "pathway_band_padding", "pathway_arrow_gap",
        "panel_canvas", "panel_margin", "panel_gutter",
        "reaction_canvas", "reaction_origin",
    }
    overlap = geometric & KNOWN_LAYOUT_PARAMS
    assert not overlap, f"Geometric keys leaked into KNOWN_LAYOUT_PARAMS: {sorted(overlap)}"


def test_load_layout_params_returns_dict():
    """load_layout_params must return a dict for each shipped preset."""
    for name in ["cell_press", "nature", "acs"]:
        params = load_layout_params(name)
        assert isinstance(params, dict), f"{name}: expected dict"


def test_load_layout_params_contains_pathway_band_fill():
    """Each shipped preset must provide pathway_band_fill in layout_overrides."""
    for name in ["cell_press", "nature", "acs"]:
        params = load_layout_params(name)
        assert "pathway_band_fill" in params, f"{name}: missing pathway_band_fill"


def test_shipped_presets_have_no_unknown_layout_keys():
    """All shipped presets must load without a UserWarning for layout_overrides."""
    import warnings as _warnings
    for name in ["cell_press", "nature", "acs"]:
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", UserWarning)
            load_preset_full(name)


def test_unknown_layout_override_key_emits_warning(tmp_path, monkeypatch):
    """A preset with a typo in layout_overrides must emit a UserWarning."""
    import warnings as _warnings
    bad = tmp_path / "bad_layout.json"
    bad.write_text(json.dumps({
        "meta": {"name": "bad_layout", "description": "test"},
        "palette": ["#" + "0" * 6] * 8,
        "overrides": {},
        "layout_overrides": {"pathway_band_colour": "#FF0000"},  # typo: colour vs color
    }))
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
    with _warnings.catch_warnings(record=True) as w:
        _warnings.simplefilter("always")
        load_preset_full("bad_layout")
    layout_warns = [x for x in w if "layout_override" in str(x.message)]
    assert len(layout_warns) == 1
    assert "pathway_band_colour" in str(layout_warns[0].message)


@pytest.mark.parametrize("preset", ["cell_press", "nature", "acs"])
def test_layout_overrides_flow_into_pathway_layout(preset):
    """layout_overrides from a preset must reach the layout engine band params."""
    from imageGen.layout.pathway_layout import layout_pathway, _compartment_band
    from tests._helpers import load_fixture
    fig = load_fixture("mapk_cascade.json")
    layout_p = load_layout_params(preset)
    entries = layout_pathway(fig, layout_params=layout_p)
    band_entries = [e for e in entries if e.primitive is _compartment_band]
    assert band_entries, "No band entries produced"
    for entry in band_entries:
        assert entry.kwargs["params"]["pathway_band_fill"] == layout_p["pathway_band_fill"]


def test_acs_layout_uses_serif_fonts():
    """ACS preset must carry serif band-label and panel-title fonts."""
    params = load_layout_params("acs")
    assert "Times" in params["pathway_band_label_family"]
    assert "Times" in params["panel_title_family"]


# ---------------------------------------------------------------------------
# Render-to-PNG goldens (3 presets × 2 fixtures = 6 files)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# V2 / ST5: KNOWN_STYLE_KEYS and unknown-key warning
# ---------------------------------------------------------------------------

def test_known_style_keys_is_nonempty_frozenset():
    """KNOWN_STYLE_KEYS must be a non-empty frozenset (ST5 guard is live)."""
    assert isinstance(KNOWN_STYLE_KEYS, frozenset)
    assert len(KNOWN_STYLE_KEYS) > 0


def test_known_style_keys_contains_core_primitives():
    """Spot-check: representative keys from each primitive module are present."""
    expected = {
        # proteins
        "protein_fill", "kinase_fill", "gpcr_helix_fill", "tf_fill",
        # arrows
        "stroke", "stroke_width", "arrow_head_size",
        # membranes
        "bilayer_head_fill", "nuclear_outer_stroke",
        # cells
        "cell_fill", "organelle_mito_fill",
        # chemistry
        "chem_bond_stroke", "chem_atom_N",
        # nucleic_acids
        "dna_strand1_stroke", "rna_stroke",
        # lab_equipment
        "tube_body_fill", "gel_lane_fill",
        # shared label keys
        "label_font_family", "label_font_size", "label_font_color",
    }
    missing = expected - KNOWN_STYLE_KEYS
    assert not missing, f"Keys missing from KNOWN_STYLE_KEYS: {sorted(missing)}"


def test_shipped_presets_have_no_unknown_keys():
    """All shipped presets (cell_press, nature, acs) must load without a warning."""
    import warnings as _warnings
    for name in ["cell_press", "nature", "acs"]:
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", UserWarning)
            load_preset_full(name)  # would raise if any key is unknown


def test_unknown_override_key_emits_warning(tmp_path, monkeypatch):
    """A preset with a typo'd key must emit a UserWarning (not raise)."""
    import warnings as _warnings
    bad = tmp_path / "typo.json"
    bad.write_text(json.dumps({
        "meta": {"name": "typo", "description": "test"},
        "palette": ["#" + "0" * 6] * 8,
        "overrides": {"protien_fill": "#FF0000"},  # deliberate typo
    }))
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
    with _warnings.catch_warnings(record=True) as w:
        _warnings.simplefilter("always")
        load_preset_full("typo")
    assert len(w) == 1
    assert issubclass(w[0].category, UserWarning)
    assert "protien_fill" in str(w[0].message)


def test_multiple_unknown_keys_all_reported(tmp_path, monkeypatch):
    """All unknown keys are reported in a single warning (not one per key)."""
    import warnings as _warnings
    bad = tmp_path / "multi.json"
    bad.write_text(json.dumps({
        "meta": {"name": "multi", "description": "test"},
        "palette": ["#" + "0" * 6] * 8,
        "overrides": {"fake_key_a": 1, "fake_key_b": 2},
    }))
    monkeypatch.setattr("imageGen.styles.loader.PRESET_DIR", tmp_path)
    with _warnings.catch_warnings(record=True) as w:
        _warnings.simplefilter("always")
        load_preset_full("multi")
    assert len(w) == 1
    msg = str(w[0].message)
    assert "fake_key_a" in msg
    assert "fake_key_b" in msg


# ---------------------------------------------------------------------------
# Render-to-PNG goldens (3 presets × 2 fixtures = 6 files)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", ["cell_press", "nature", "acs"])
def test_render_mapk_with_preset(preset):
    fig = load_fixture("mapk_cascade.json")
    style = load_style(preset)
    entries = layout_pathway(fig, style_dict=style)
    out = render_entries_to_png(entries, f"style_{preset}_mapk.png")
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.parametrize("preset", ["cell_press", "nature", "acs"])
def test_render_oxidation_with_preset(preset):
    fig = load_fixture("oxidation_reaction.json")
    style = load_style(preset)
    entries = layout_reaction(fig, smiles_map=_OXIDATION_SMILES, style_dict=style)
    out = render_entries_to_png(entries, f"style_{preset}_oxidation.png")
    assert out.exists() and out.stat().st_size > 0
