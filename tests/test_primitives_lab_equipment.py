"""Phase 2 Step 7 tests for primitives/lab_equipment.py."""
from __future__ import annotations

import pytest
import svgwrite
import svgwrite.container

from primitives.lab_equipment import (
    DEFAULT_STYLE,
    _MICROSCOPE_STYLES,
    _TUBE_BUILDERS,
    gel_full,
    gel_lane,
    human_figure,
    microscope,
    mouse,
    pipette,
    stick_figure_dog,
    tube,
    well_plate,
)
from tests._helpers import render_group_to_png


# ---------------------------------------------------------------------------
# DEFAULT_STYLE completeness
# ---------------------------------------------------------------------------

def test_default_style_has_all_namespaced_keys():
    required = {
        "lab_outline_stroke", "lab_outline_stroke_width",
        "well_radius", "well_gap", "well_stroke", "well_stroke_width",
        "well_default_fill",
        "plate_corner_radius", "plate_padding", "plate_outline_stroke",
        "plate_outline_stroke_width", "plate_fill",
        "tube_eppendorf_width", "tube_eppendorf_height",
        "tube_falcon_width", "tube_falcon_height",
        "tube_pcr_width", "tube_pcr_height",
        "tube_cap_height", "tube_cap_fill", "tube_body_fill",
        "tube_contents_opacity",
        "pipette_body_width", "pipette_body_height", "pipette_tip_height",
        "pipette_button_height", "pipette_body_fill", "pipette_button_fill",
        "gel_lane_width", "gel_lane_height", "gel_lane_fill",
        "gel_lane_stroke", "gel_lane_stroke_width",
        "gel_band_default_color", "gel_band_height", "gel_lane_gap",
        "gel_ladder_label_font_size", "gel_ladder_label_color",
        "microscope_body_w", "microscope_body_h",
        "microscope_eyepiece_w", "microscope_eyepiece_h",
        "microscope_stage_w", "microscope_stage_h", "microscope_objective_h",
        "microscope_body_fill", "microscope_accent_light",
        "microscope_accent_fluorescence", "microscope_accent_em",
        "mouse_body_color", "mouse_ear_color", "mouse_eye_color",
        "mouse_tail_color", "mouse_tail_width",
        "human_color", "human_stroke_width", "human_head_radius",
        "dog_body_color", "dog_outline_color", "dog_outline_width",
        "dog_eye_color", "dog_tongue_color",
        "label_font_family", "label_font_size", "label_font_color",
    }
    assert required <= set(DEFAULT_STYLE.keys())


# ---------------------------------------------------------------------------
# well_plate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rows,cols", [(8, 12), (16, 24)])
def test_well_plate_returns_group(rows, cols):
    g = well_plate(rows=rows, cols=cols)
    assert isinstance(g, svgwrite.container.Group)


def test_well_plate_highlights_appear_in_svg():
    g = well_plate(highlights={(0, 0): "#FF00FF", (3, 5): "#00FF00"})
    dwg = svgwrite.Drawing(size=("400px", "300px"))
    dwg.add(g)
    s = dwg.tostring()
    assert "#FF00FF" in s.upper()
    assert "#00FF00" in s.upper()


def test_well_plate_invalid_highlight_raises():
    with pytest.raises(ValueError, match="outside"):
        well_plate(highlights={(99, 99): "#FF0000"})


# ---------------------------------------------------------------------------
# tube
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tube_type", sorted(_TUBE_BUILDERS))
def test_tube_each_type(tube_type):
    g = tube(type=tube_type, label=tube_type)
    assert isinstance(g, svgwrite.container.Group)


def test_tube_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown tube type"):
        tube(type="bogus")


def test_tube_with_contents_color_appears_in_svg():
    g = tube(type="eppendorf", contents_color="#FF8800")
    dwg = svgwrite.Drawing(size=("100px", "100px"))
    dwg.add(g)
    assert "#FF8800" in dwg.tostring().upper()


# ---------------------------------------------------------------------------
# pipette
# ---------------------------------------------------------------------------

def test_pipette_returns_group():
    assert isinstance(pipette(), svgwrite.container.Group)


def test_pipette_with_volume_label_appears_in_svg():
    g = pipette(volume="200 uL")
    dwg = svgwrite.Drawing(size=("200px", "200px"))
    dwg.add(g)
    assert "200 uL" in dwg.tostring()


# ---------------------------------------------------------------------------
# gel_lane / gel_full
# ---------------------------------------------------------------------------

def test_gel_lane_with_bands():
    g = gel_lane(bands=[(0.2, 0.9), (0.5, 0.6), (0.8, 0.3)])
    assert isinstance(g, svgwrite.container.Group)


def test_gel_lane_empty_bands():
    assert isinstance(gel_lane(bands=[]), svgwrite.container.Group)


def test_gel_full_with_ladder():
    g = gel_full(
        lanes=[[(0.2, 0.9)], [(0.3, 0.7), (0.6, 0.5)], [(0.5, 0.8)]],
        ladder=[(0.1, "1kb"), (0.3, "500"), (0.6, "200")],
    )
    dwg = svgwrite.Drawing(size=("400px", "200px"))
    dwg.add(g)
    s = dwg.tostring()
    assert "1kb" in s
    assert "500" in s


# ---------------------------------------------------------------------------
# microscope
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scope_style", sorted(_MICROSCOPE_STYLES))
@pytest.mark.parametrize("minimal", [True, False])
def test_microscope_each_style(scope_style, minimal):
    g = microscope(style=scope_style, minimal=minimal)
    assert isinstance(g, svgwrite.container.Group)


def test_microscope_unknown_style_raises():
    with pytest.raises(ValueError, match="Unknown microscope style"):
        microscope(style="electron-tunneling")


# ---------------------------------------------------------------------------
# mouse / human / dog
# ---------------------------------------------------------------------------

def test_mouse_returns_group():
    assert isinstance(mouse(), svgwrite.container.Group)


def test_mouse_with_strain_label_appears_in_svg():
    g = mouse(strain_label="C57BL/6")
    dwg = svgwrite.Drawing(size=("200px", "200px"))
    dwg.add(g)
    assert "C57BL/6" in dwg.tostring()


@pytest.mark.parametrize("minimal", [True, False])
def test_human_figure_returns_group(minimal):
    assert isinstance(human_figure(minimal=minimal), svgwrite.container.Group)


def test_stick_figure_dog_returns_group():
    assert isinstance(stick_figure_dog(), svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Style override flows through
# ---------------------------------------------------------------------------

def test_style_override_does_not_crash():
    overrides = {"lab_outline_stroke": "#FF0000", "lab_outline_stroke_width": 3.0,
                 "well_radius": 6.0, "dog_body_color": "#00FFAA"}
    well_plate(style_dict=overrides)
    tube(type="eppendorf", style_dict=overrides)
    pipette(style_dict=overrides)
    gel_lane(bands=[(0.5, 0.5)], style_dict=overrides)
    gel_full(lanes=[[(0.5, 0.5)]], style_dict=overrides)
    microscope(style_dict=overrides)
    mouse(style_dict=overrides)
    human_figure(style_dict=overrides)
    stick_figure_dog(style_dict=overrides)


# ---------------------------------------------------------------------------
# Render-to-PNG fixtures (Phase 6 golden-image seeds)
# ---------------------------------------------------------------------------

def test_lab_equipment_renders_to_png():
    render_group_to_png(well_plate(highlights={(0, 0): "#42A5F5", (3, 5): "#EF5350",
                                           (7, 11): "#66BB6A"}),
                   "lab_well_plate_96.png", canvas=(220, 160))
    render_group_to_png(well_plate(rows=16, cols=24),
                   "lab_well_plate_384.png", canvas=(360, 250))
    for t in ("eppendorf", "falcon", "pcr"):
        render_group_to_png(tube(type=t, label=t, contents_color="#FFC107"),
                       f"lab_tube_{t}.png", canvas=(80, 120))
    render_group_to_png(pipette(volume="200 uL"),
                   "lab_pipette.png", canvas=(120, 130))
    render_group_to_png(
        gel_full(
            lanes=[[(0.2, 0.9), (0.5, 0.6)],
                   [(0.3, 0.8), (0.55, 0.5), (0.75, 0.3)],
                   [(0.4, 0.7)],
                   [(0.25, 0.85), (0.6, 0.4)]],
            ladder=[(0.1, "1kb"), (0.25, "500"), (0.5, "200"), (0.75, "100")],
        ),
        "lab_gel_full.png",
        canvas=(220, 130),
    )
    for s in ("light", "fluorescence", "em"):
        render_group_to_png(microscope(style=s, minimal=False),
                       f"lab_microscope_{s}.png", canvas=(100, 100))
    render_group_to_png(mouse(strain_label="C57BL/6"),
                   "lab_mouse.png", canvas=(140, 80))
    render_group_to_png(human_figure(minimal=True),
                   "lab_human_minimal.png", canvas=(80, 90))
    render_group_to_png(human_figure(minimal=False),
                   "lab_human_silhouette.png", canvas=(80, 90))
    render_group_to_png(stick_figure_dog(),
                   "lab_stick_figure_dog.png", canvas=(140, 100))
