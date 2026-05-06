"""Lab-equipment primitives for scientific figure generation.

Schematic icons used in methods figures, workflow diagrams, and graphical
abstracts. These are *icons*, not biologically-rendered shapes -- they should
be recognizable without a label and read clearly at small sizes.

Icons in this module:
- well_plate: 96-well by default; pass (rows=16, cols=24) for 384-well or
  (32, 48) for 1536-well -- no code change needed
- tube: eppendorf | falcon | pcr (dispatched via _TUBE_BUILDERS)
- pipette: vertical body + tip + plunger
- gel_lane / gel_full: bands at vertical positions with intensity-modulated
  opacity; gel_full composes lanes side-by-side with optional ladder
- microscope: light | fluorescence | em (dispatched via _MICROSCOPE_BUILDERS),
  with minimal=True collapsing to a simplified silhouette
- mouse, human_figure, stick_figure_dog: subject silhouettes for in-vivo /
  clinical / general schematics. The dog is deliberately cute.

Composability:
  All icons draw at local origin then translate via the Group's transform.
  No background fill -- canvas remains transparent so icons can overlay any
  other primitive (same convention as chemistry.py overlay support). All
  shapes are native svgwrite elements (no nested <svg>), so overflow
  handling is irrelevant here.

Phase 3 coupling:
  Lab equipment is point-anchored (caller passes `position=(x,y)`) -- no
  curve protocol. Layout code positions icons by absolute coordinate.

Future extensibility:
  - New tube types: add a key to _TUBE_BUILDERS and a `_<type>_tube()` helper
  - New microscope types: same pattern via _MICROSCOPE_BUILDERS
  - Larger plates: pass any (rows, cols); plate dimensions scale automatically
"""
from __future__ import annotations

from typing import Callable, Literal, Optional

import svgwrite
import svgwrite.container
import svgwrite.path
import svgwrite.shapes
import svgwrite.text


# ---------------------------------------------------------------------------
# Style defaults -- flat namespaced keys for Phase 4 preset union
# ---------------------------------------------------------------------------

DEFAULT_STYLE: dict[str, object] = {
    # Shared
    "lab_outline_stroke":            "#37474F",
    "lab_outline_stroke_width":       1.5,
    # Well plate
    "well_radius":                    4.0,
    "well_gap":                       2.0,
    "well_stroke":                   "#546E7A",
    "well_stroke_width":              0.8,
    "well_default_fill":             "#FFFFFF",
    "plate_corner_radius":            6.0,
    "plate_padding":                  10.0,
    "plate_outline_stroke":          "#37474F",
    "plate_outline_stroke_width":     1.5,
    "plate_fill":                    "#CFD8DC",
    # Tubes
    "tube_eppendorf_width":           20.0,
    "tube_eppendorf_height":          40.0,
    "tube_falcon_width":              22.0,
    "tube_falcon_height":             80.0,
    "tube_pcr_width":                 14.0,
    "tube_pcr_height":                28.0,
    "tube_cap_height":                6.0,
    "tube_cap_fill":                 "#90A4AE",
    "tube_body_fill":                "#FFFFFF",
    "tube_contents_opacity":          0.85,
    # Pipette
    "pipette_body_width":             10.0,
    "pipette_body_height":            70.0,
    "pipette_tip_height":             18.0,
    "pipette_button_height":          8.0,
    "pipette_body_fill":             "#FFFFFF",
    "pipette_button_fill":           "#1565C0",
    # Gel
    "gel_lane_width":                 24.0,
    "gel_lane_height":                100.0,
    "gel_lane_fill":                 "#263238",
    "gel_lane_stroke":               "#000000",
    "gel_lane_stroke_width":          1.0,
    "gel_band_default_color":        "#B0BEC5",
    "gel_band_height":                4.0,
    "gel_lane_gap":                   4.0,
    "gel_ladder_label_font_size":     8,
    "gel_ladder_label_color":        "#FFFFFF",
    # Microscope
    "microscope_body_w":              50.0,
    "microscope_body_h":              60.0,
    "microscope_eyepiece_w":          18.0,
    "microscope_eyepiece_h":          14.0,
    "microscope_stage_w":             40.0,
    "microscope_stage_h":             6.0,
    "microscope_objective_h":         12.0,
    "microscope_body_fill":          "#B0BEC5",
    "microscope_accent_light":       "#FFD54F",
    "microscope_accent_fluorescence": "#26C6DA",
    "microscope_accent_em":          "#78909C",
    # Mouse
    "mouse_body_color":              "#D7CCC8",
    "mouse_ear_color":               "#A1887F",
    "mouse_eye_color":               "#212121",
    "mouse_tail_color":              "#A1887F",
    "mouse_tail_width":               1.5,
    # Human figure
    "human_color":                   "#37474F",
    "human_stroke_width":             2.5,
    "human_head_radius":              7.0,
    # Dog (deliberately cute)
    "dog_body_color":                "#FFB74D",
    "dog_outline_color":             "#5D4037",
    "dog_outline_width":              2.0,
    "dog_eye_color":                 "#212121",
    "dog_tongue_color":              "#E57373",
    # Shared label
    "label_font_family":             "Helvetica, Arial, sans-serif",
    "label_font_size":                11,
    "label_font_color":              "#1A1A1A",
}


TubeType = Literal["eppendorf", "falcon", "pcr"]
MicroscopeStyle = Literal["light", "fluorescence", "em"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _rounded_rect(
    insert: tuple[float, float],
    size: tuple[float, float],
    rx: float = 0.0,
    **kw,
) -> svgwrite.shapes.Rect:
    """Rect with consistent corner-rounding signature."""
    return svgwrite.shapes.Rect(insert=insert, size=size, rx=rx, ry=rx, **kw)


def _label_below(
    group: svgwrite.container.Group,
    text: str,
    anchor_xy: tuple[float, float],
    style: dict,
) -> None:
    """Append a centered text label at *anchor_xy* (typically icon's bottom-center)."""
    if not text:
        return
    group.add(svgwrite.text.Text(
        text,
        insert=anchor_xy,
        font_size=int(style["label_font_size"]),
        fill=str(style["label_font_color"]),
        font_family=str(style["label_font_family"]),
        text_anchor="middle",
    ))


# ---------------------------------------------------------------------------
# Tube dispatch + builders
# ---------------------------------------------------------------------------

def _eppendorf_tube(
    contents_color: Optional[str], style: dict,
) -> tuple[svgwrite.container.Group, tuple[float, float]]:
    """Return (group, (width, height)) for an eppendorf tube at local origin."""
    g = svgwrite.container.Group()
    w = float(style["tube_eppendorf_width"])
    h = float(style["tube_eppendorf_height"])
    cap_h = float(style["tube_cap_height"])
    stroke = str(style["lab_outline_stroke"])
    sw = float(style["lab_outline_stroke_width"])
    g.add(_rounded_rect((0, 0), (w, cap_h), rx=2.0,
                        fill=str(style["tube_cap_fill"]), stroke=stroke, stroke_width=sw))
    body_top = cap_h
    body_h_rect = h * 0.6 - cap_h
    g.add(_rounded_rect((0, body_top), (w, body_h_rect), rx=1.5,
                        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw))
    cone_top_y = body_top + body_h_rect
    cone_bot_y = h
    g.add(svgwrite.shapes.Polygon(
        points=[(0, cone_top_y), (w, cone_top_y), (w / 2.0, cone_bot_y)],
        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw,
    ))
    if contents_color:
        contents_top = body_top + body_h_rect * 0.4
        g.add(_rounded_rect((1.0, contents_top), (w - 2.0, body_h_rect * 0.6 - 1.0),
                            rx=1.0, fill=contents_color,
                            opacity=float(style["tube_contents_opacity"]),
                            stroke="none"))
        g.add(svgwrite.shapes.Polygon(
            points=[(1.0, cone_top_y), (w - 1.0, cone_top_y),
                    (w / 2.0, cone_bot_y - 1.0)],
            fill=contents_color, opacity=float(style["tube_contents_opacity"]),
            stroke="none",
        ))
    return g, (w, h)


def _falcon_tube(
    contents_color: Optional[str], style: dict,
) -> tuple[svgwrite.container.Group, tuple[float, float]]:
    g = svgwrite.container.Group()
    w = float(style["tube_falcon_width"])
    h = float(style["tube_falcon_height"])
    cap_h = float(style["tube_cap_height"])
    stroke = str(style["lab_outline_stroke"])
    sw = float(style["lab_outline_stroke_width"])
    g.add(_rounded_rect((-1.0, 0), (w + 2.0, cap_h), rx=2.0,
                        fill=str(style["tube_cap_fill"]), stroke=stroke, stroke_width=sw))
    body_top = cap_h
    body_h_rect = h * 0.78 - cap_h
    g.add(_rounded_rect((0, body_top), (w, body_h_rect), rx=1.5,
                        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw))
    cone_top_y = body_top + body_h_rect
    g.add(svgwrite.shapes.Polygon(
        points=[(0, cone_top_y), (w, cone_top_y), (w / 2.0, h)],
        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw,
    ))
    if contents_color:
        contents_top = body_top + body_h_rect * 0.5
        g.add(_rounded_rect((1.0, contents_top), (w - 2.0, body_h_rect * 0.5 - 1.0),
                            rx=1.0, fill=contents_color,
                            opacity=float(style["tube_contents_opacity"]),
                            stroke="none"))
    return g, (w, h)


def _pcr_tube(
    contents_color: Optional[str], style: dict,
) -> tuple[svgwrite.container.Group, tuple[float, float]]:
    g = svgwrite.container.Group()
    w = float(style["tube_pcr_width"])
    h = float(style["tube_pcr_height"])
    cap_h = float(style["tube_cap_height"])
    stroke = str(style["lab_outline_stroke"])
    sw = float(style["lab_outline_stroke_width"])
    g.add(_rounded_rect((0, 0), (w, cap_h), rx=1.5,
                        fill=str(style["tube_cap_fill"]), stroke=stroke, stroke_width=sw))
    body_top = cap_h
    body_h_rect = h * 0.55 - cap_h
    g.add(_rounded_rect((0, body_top), (w, body_h_rect), rx=1.0,
                        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw))
    cone_top_y = body_top + body_h_rect
    g.add(svgwrite.shapes.Polygon(
        points=[(0, cone_top_y), (w, cone_top_y), (w / 2.0, h)],
        fill=str(style["tube_body_fill"]), stroke=stroke, stroke_width=sw,
    ))
    if contents_color:
        g.add(_rounded_rect((1.0, body_top + body_h_rect * 0.35),
                            (w - 2.0, body_h_rect * 0.65 - 1.0), rx=0.8,
                            fill=contents_color,
                            opacity=float(style["tube_contents_opacity"]),
                            stroke="none"))
    return g, (w, h)


_TUBE_BUILDERS: dict[str, Callable] = {
    "eppendorf": _eppendorf_tube,
    "falcon":    _falcon_tube,
    "pcr":       _pcr_tube,
}


# ---------------------------------------------------------------------------
# Microscope dispatch + builders
# ---------------------------------------------------------------------------

def _microscope_common(accent_color: str, minimal: bool, style: dict) -> svgwrite.container.Group:
    g = svgwrite.container.Group()
    bw = float(style["microscope_body_w"])
    bh = float(style["microscope_body_h"])
    ew = float(style["microscope_eyepiece_w"])
    eh = float(style["microscope_eyepiece_h"])
    sw_stage = float(style["microscope_stage_w"])
    sh_stage = float(style["microscope_stage_h"])
    obj_h = float(style["microscope_objective_h"])
    stroke = str(style["lab_outline_stroke"])
    lsw = float(style["lab_outline_stroke_width"])
    body_fill = str(style["microscope_body_fill"])

    eyepiece_x = (bw - ew) / 2.0
    g.add(_rounded_rect((eyepiece_x, 0), (ew, eh), rx=2.0,
                        fill=body_fill, stroke=stroke, stroke_width=lsw))
    body_top = eh
    g.add(_rounded_rect((0, body_top), (bw, bh - eh - sh_stage - obj_h), rx=4.0,
                        fill=body_fill, stroke=stroke, stroke_width=lsw))
    obj_y = body_top + (bh - eh - sh_stage - obj_h)
    if not minimal:
        turret_w = bw * 0.6
        g.add(svgwrite.shapes.Circle(
            center=(bw / 2.0, obj_y + obj_h / 2.0), r=turret_w / 2.0,
            fill=body_fill, stroke=stroke, stroke_width=lsw,
        ))
    g.add(_rounded_rect((bw / 2.0 - 3.0, obj_y + obj_h * 0.4),
                        (6.0, obj_h * 0.6), rx=1.0,
                        fill=accent_color, stroke=stroke, stroke_width=lsw))
    stage_x = (bw - sw_stage) / 2.0
    stage_y = bh - sh_stage
    g.add(_rounded_rect((stage_x, stage_y), (sw_stage, sh_stage), rx=1.0,
                        fill=body_fill, stroke=stroke, stroke_width=lsw))
    return g


_MICROSCOPE_STYLES: tuple[str, ...] = ("light", "fluorescence", "em")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def well_plate(
    rows: int = 8,
    cols: int = 12,
    highlights: dict[tuple[int, int], str] | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a microtiter plate. Default 8x12 = 96-well; pass (16, 24) for 384.

    Args:
        rows, cols: well grid dimensions.
        highlights: optional {(row, col): color_hex} for per-well highlighting;
            keys must satisfy 0 <= row < rows and 0 <= col < cols.
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the plate outline + well grid, anchored at *position*.

    Raises:
        ValueError: any highlight key falls outside the grid.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    highlights = highlights or {}
    for (r, c) in highlights:
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"Highlight ({r},{c}) outside {rows}x{cols} plate")

    radius = float(style["well_radius"])
    gap = float(style["well_gap"])
    pad = float(style["plate_padding"])
    cell = 2 * radius + gap
    plate_w = pad * 2 + cols * cell - gap
    plate_h = pad * 2 + rows * cell - gap

    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    g.add(_rounded_rect((0, 0), (plate_w, plate_h),
                        rx=float(style["plate_corner_radius"]),
                        fill=str(style["plate_fill"]),
                        stroke=str(style["plate_outline_stroke"]),
                        stroke_width=float(style["plate_outline_stroke_width"])))
    well_stroke = str(style["well_stroke"])
    well_sw = float(style["well_stroke_width"])
    default_fill = str(style["well_default_fill"])
    for r in range(rows):
        for c in range(cols):
            cx = pad + c * cell + radius
            cy = pad + r * cell + radius
            fill = highlights.get((r, c), default_fill)
            g.add(svgwrite.shapes.Circle(
                center=(cx, cy), r=radius,
                fill=fill, stroke=well_stroke, stroke_width=well_sw,
            ))
    return g


def tube(
    type: TubeType = "eppendorf",
    label: str = "",
    contents_color: str | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a lab tube.

    Args:
        type: 'eppendorf' (1.5mL conical), 'falcon' (15/50mL conical with cap),
            or 'pcr' (thin-walled).
        label: optional text rendered below the tube.
        contents_color: optional fill color for the lower (liquid) region.
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the tube and optional label.

    Raises:
        ValueError: *type* is not a known tube type.
    """
    if type not in _TUBE_BUILDERS:
        valid = ", ".join(sorted(_TUBE_BUILDERS))
        raise ValueError(f"Unknown tube type {type!r} (valid: {valid})")
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    body, (w, h) = _TUBE_BUILDERS[type](contents_color, style)
    g.add(body)
    _label_below(g, label, (w / 2.0, h + int(style["label_font_size"]) + 2), style)
    return g


def pipette(
    volume: str = "",
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a vertical pipette icon with optional volume label.

    Args:
        volume: text rendered to the right of the pipette body (e.g. '200 uL').
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the pipette body, tip, plunger button, and label.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    bw = float(style["pipette_body_width"])
    bh = float(style["pipette_body_height"])
    tip_h = float(style["pipette_tip_height"])
    btn_h = float(style["pipette_button_height"])
    stroke = str(style["lab_outline_stroke"])
    sw = float(style["lab_outline_stroke_width"])
    g.add(_rounded_rect((0, 0), (bw, btn_h), rx=2.0,
                        fill=str(style["pipette_button_fill"]), stroke=stroke, stroke_width=sw))
    g.add(_rounded_rect((0, btn_h), (bw, bh), rx=2.0,
                        fill=str(style["pipette_body_fill"]), stroke=stroke, stroke_width=sw))
    tip_top_y = btn_h + bh
    g.add(svgwrite.shapes.Polygon(
        points=[(0, tip_top_y), (bw, tip_top_y), (bw / 2.0, tip_top_y + tip_h)],
        fill=str(style["pipette_body_fill"]), stroke=stroke, stroke_width=sw,
    ))
    if volume:
        g.add(svgwrite.text.Text(
            volume,
            insert=(bw + 4, btn_h + bh / 2.0),
            font_size=int(style["label_font_size"]),
            fill=str(style["label_font_color"]),
            font_family=str(style["label_font_family"]),
        ))
    return g


def gel_lane(
    bands: list[tuple[float, float]] | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
    band_color: str | None = None,
) -> svgwrite.container.Group:
    """Render one gel lane with optional bands.

    Args:
        bands: list of (y_fraction, intensity) where y_fraction in [0,1] is the
            band's vertical position (0 = top of lane, 1 = bottom) and intensity
            in [0,1] sets the band fill opacity.
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.
        band_color: optional override for band fill color (default from style).

    Returns:
        Group containing the lane outline and band rects.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    bands = bands or []
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    w = float(style["gel_lane_width"])
    h = float(style["gel_lane_height"])
    g.add(_rounded_rect((0, 0), (w, h), rx=1.0,
                        fill=str(style["gel_lane_fill"]),
                        stroke=str(style["gel_lane_stroke"]),
                        stroke_width=float(style["gel_lane_stroke_width"])))
    band_h = float(style["gel_band_height"])
    fill = band_color or str(style["gel_band_default_color"])
    for y_frac, intensity in bands:
        y = max(0.0, min(1.0, y_frac)) * (h - band_h)
        g.add(_rounded_rect((1.0, y), (w - 2.0, band_h), rx=0.8,
                            fill=fill, opacity=max(0.0, min(1.0, intensity)),
                            stroke="none"))
    return g


def gel_full(
    lanes: list[list[tuple[float, float]]],
    ladder: list[tuple[float, str]] | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a full gel: optional ladder lane on the left, then numbered lanes.

    Args:
        lanes: list of band lists; each inner list has the same shape as the
            `bands` arg of gel_lane.
        ladder: optional [(y_fraction, label), ...] for the leftmost reference lane.
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing all lanes side-by-side.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    lane_w = float(style["gel_lane_width"])
    gap = float(style["gel_lane_gap"])
    cursor_x = 0.0
    if ladder:
        ladder_bands = [(y, 1.0) for y, _ in ladder]
        g.add(gel_lane(ladder_bands, position=(cursor_x, 0.0), style_dict=style))
        for y_frac, label in ladder:
            y = max(0.0, min(1.0, y_frac)) * float(style["gel_lane_height"])
            g.add(svgwrite.text.Text(
                label,
                insert=(cursor_x + lane_w / 2.0, y),
                font_size=int(style["gel_ladder_label_font_size"]),
                fill=str(style["gel_ladder_label_color"]),
                font_family=str(style["label_font_family"]),
                text_anchor="middle",
            ))
        cursor_x += lane_w + gap
    for lane_bands in lanes:
        g.add(gel_lane(lane_bands, position=(cursor_x, 0.0), style_dict=style))
        cursor_x += lane_w + gap
    return g


def microscope(
    style: MicroscopeStyle = "light",
    minimal: bool = True,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a microscope icon.

    Args:
        style: 'light' (yellow accent), 'fluorescence' (cyan accent), or 'em'
            (gray-metallic accent). Color-codes the objective region.
        minimal: True drops the objective turret detail; False adds it.
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the microscope icon.

    Raises:
        ValueError: *style* is not a known microscope type.
    """
    if style not in _MICROSCOPE_STYLES:
        valid = ", ".join(sorted(_MICROSCOPE_STYLES))
        raise ValueError(f"Unknown microscope style {style!r} (valid: {valid})")
    merged_style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    accent = str(merged_style[f"microscope_accent_{style}"])
    g.add(_microscope_common(accent, minimal, merged_style))
    return g


def mouse(
    strain_label: str | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a side-view mouse silhouette with optional strain label.

    Args:
        strain_label: optional text rendered below the mouse (e.g. 'C57BL/6').
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the mouse silhouette and optional label.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    body_color = str(style["mouse_body_color"])
    body_w, body_h = 60.0, 28.0
    g.add(svgwrite.shapes.Ellipse(
        center=(body_w / 2.0, body_h / 2.0), r=(body_w / 2.0, body_h / 2.0),
        fill=body_color, stroke=str(style["lab_outline_stroke"]),
        stroke_width=float(style["lab_outline_stroke_width"]),
    ))
    head_cx, head_cy, head_r = body_w + 6.0, body_h / 2.0, 9.0
    g.add(svgwrite.shapes.Circle(
        center=(head_cx, head_cy), r=head_r,
        fill=body_color, stroke=str(style["lab_outline_stroke"]),
        stroke_width=float(style["lab_outline_stroke_width"]),
    ))
    g.add(svgwrite.shapes.Circle(
        center=(head_cx - 1.0, head_cy - 4.0), r=3.5,
        fill=str(style["mouse_ear_color"]), stroke=str(style["lab_outline_stroke"]),
        stroke_width=float(style["lab_outline_stroke_width"]),
    ))
    g.add(svgwrite.shapes.Circle(
        center=(head_cx + 3.0, head_cy + 1.0), r=1.2,
        fill=str(style["mouse_eye_color"]), stroke="none",
    ))
    g.add(svgwrite.shapes.Polyline(
        points=[(0.0, body_h / 2.0), (-12.0, body_h / 2.0 + 4.0),
                (-18.0, body_h / 2.0 - 2.0)],
        fill="none", stroke=str(style["mouse_tail_color"]),
        stroke_width=float(style["mouse_tail_width"]),
    ))
    icon_h = body_h
    _label_below(g, strain_label or "",
                 (body_w / 2.0, icon_h + int(style["label_font_size"]) + 4), style)
    return g


def human_figure(
    minimal: bool = True,
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Render a human figure: stick (minimal=True) or simple silhouette.

    Args:
        minimal: True for stick figure; False for silhouette (head + body rect).
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the figure.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    color = str(style["human_color"])
    sw = float(style["human_stroke_width"])
    head_r = float(style["human_head_radius"])
    cx = 20.0
    head_cy = head_r
    g.add(svgwrite.shapes.Circle(
        center=(cx, head_cy), r=head_r,
        fill="none" if minimal else color, stroke=color, stroke_width=sw,
    ))
    if minimal:
        body_top = head_cy + head_r
        body_bot = body_top + 22.0
        g.add(svgwrite.shapes.Line(start=(cx, body_top), end=(cx, body_bot),
                                   stroke=color, stroke_width=sw))
        g.add(svgwrite.shapes.Line(start=(cx - 12, body_top + 6),
                                   end=(cx + 12, body_top + 6),
                                   stroke=color, stroke_width=sw))
        g.add(svgwrite.shapes.Line(start=(cx, body_bot),
                                   end=(cx - 9, body_bot + 14),
                                   stroke=color, stroke_width=sw))
        g.add(svgwrite.shapes.Line(start=(cx, body_bot),
                                   end=(cx + 9, body_bot + 14),
                                   stroke=color, stroke_width=sw))
    else:
        body_top = head_cy + head_r
        g.add(_rounded_rect((cx - 9, body_top), (18, 28), rx=4.0,
                            fill=color, stroke=color, stroke_width=sw))
        g.add(_rounded_rect((cx - 4, body_top + 28), (3.5, 16), rx=1.5,
                            fill=color, stroke=color, stroke_width=sw))
        g.add(_rounded_rect((cx + 0.5, body_top + 28), (3.5, 16), rx=1.5,
                            fill=color, stroke=color, stroke_width=sw))
    return g


def stick_figure_dog(
    position: tuple[float, float] = (0.0, 0.0),
    style_dict: dict | None = None,
) -> svgwrite.container.Group:
    """Cute stick-figure dog: round head + nose, triangle ears, oval body, four
    legs, curl tail, dot eyes, tongue. Joey wanted this.

    Args:
        position: (x, y) translation applied to the Group.
        style_dict: optional preset overlay; merged onto DEFAULT_STYLE.

    Returns:
        Group containing the dog.
    """
    style = {**DEFAULT_STYLE, **(style_dict or {})}
    g = svgwrite.container.Group(transform=f"translate({position[0]},{position[1]})")
    body_color = str(style["dog_body_color"])
    outline = str(style["dog_outline_color"])
    osw = float(style["dog_outline_width"])
    body_cx, body_cy, body_rx, body_ry = 30.0, 30.0, 22.0, 12.0
    g.add(svgwrite.shapes.Ellipse(
        center=(body_cx, body_cy), r=(body_rx, body_ry),
        fill=body_color, stroke=outline, stroke_width=osw,
    ))
    head_cx, head_cy, head_r = body_cx + body_rx + 4.0, body_cy - 4.0, 12.0
    g.add(svgwrite.shapes.Circle(
        center=(head_cx, head_cy), r=head_r,
        fill=body_color, stroke=outline, stroke_width=osw,
    ))
    nose_cx, nose_cy, nose_r = head_cx + head_r * 0.8, head_cy + 2.0, 4.5
    g.add(svgwrite.shapes.Circle(
        center=(nose_cx, nose_cy), r=nose_r,
        fill=body_color, stroke=outline, stroke_width=osw,
    ))
    g.add(svgwrite.shapes.Circle(
        center=(nose_cx + nose_r - 1.0, nose_cy - 0.5), r=1.4,
        fill=outline, stroke="none",
    ))
    g.add(svgwrite.shapes.Polygon(
        points=[(head_cx - 6, head_cy - head_r),
                (head_cx - 1, head_cy - head_r - 7),
                (head_cx + 2, head_cy - head_r + 1)],
        fill=body_color, stroke=outline, stroke_width=osw,
    ))
    g.add(svgwrite.shapes.Polygon(
        points=[(head_cx + 4, head_cy - head_r + 1),
                (head_cx + 8, head_cy - head_r - 5),
                (head_cx + 11, head_cy - head_r + 2)],
        fill=body_color, stroke=outline, stroke_width=osw,
    ))
    g.add(svgwrite.shapes.Circle(
        center=(head_cx + 1.5, head_cy - 1.5), r=1.4,
        fill=str(style["dog_eye_color"]), stroke="none",
    ))
    g.add(svgwrite.shapes.Circle(
        center=(head_cx + 7.5, head_cy - 1.5), r=1.4,
        fill=str(style["dog_eye_color"]), stroke="none",
    ))
    g.add(svgwrite.shapes.Line(
        start=(nose_cx, nose_cy + nose_r - 0.5),
        end=(nose_cx + 1, nose_cy + nose_r + 4),
        stroke=str(style["dog_tongue_color"]), stroke_width=2.0,
    ))
    leg_y_top = body_cy + body_ry - 2.0
    leg_y_bot = leg_y_top + 12.0
    for leg_x in (body_cx - body_rx + 4, body_cx - 5,
                  body_cx + 5, body_cx + body_rx - 4):
        g.add(svgwrite.shapes.Line(
            start=(leg_x, leg_y_top), end=(leg_x, leg_y_bot),
            stroke=outline, stroke_width=osw,
        ))
    g.add(svgwrite.path.Path(
        d=f"M {body_cx - body_rx} {body_cy - 2} "
          f"q -8 -4 -4 -10 q 4 -4 7 2",
        fill="none", stroke=outline, stroke_width=osw,
    ))
    return g
