"""Format converters for the renderer — Phase 5 Step 4.

Thin `cairosvg` wrappers used by `render_figure` when the requested output
format is not SVG. The compositor writes an SVG first; these functions
convert that SVG file into a PNG or PDF on disk.

Our SVGs are emitted with pixel dimensions (assumed at the CSS-standard
96 dpi), so cairosvg's `dpi` kwarg alone — which only resolves physical
units like cm/in — does not change output pixel count. To make the `dpi`
parameter user-facing-meaningful for journal-quality output, we also pass
`scale = dpi / 96`. Result: dpi=300 yields a PNG ~3.125× the SVG's
pixel-width dimensions, the conventional 300-dpi mapping.

For PDF, vector geometry is resolution-independent; `dpi` only affects
any embedded raster bitmaps. Scale is still forwarded for consistency
with PNG and so that any embedded rasters render at the same effective
density.
"""
from __future__ import annotations

from pathlib import Path

import cairosvg

_CSS_DPI = 96.0  # cairosvg / CSS default user-unit DPI for length resolution


def _scale_for_dpi(dpi: int) -> float:
    return dpi / _CSS_DPI


def svg_to_png(svg_path: Path, output_path: Path, dpi: int = 300) -> Path:
    """Convert an SVG file to PNG via cairosvg.

    Args:
        svg_path: Path to an existing SVG file.
        output_path: Destination PNG path.
        dpi: Output resolution in dots-per-inch (default 300, journal
            quality). Forwarded to cairosvg both as the length-unit
            resolution and as a `dpi/96` scale factor on the output
            pixel grid.

    Returns:
        Path to the written PNG (== output_path).
    """
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(output_path),
        dpi=dpi,
        scale=_scale_for_dpi(dpi),
    )
    return output_path


def svg_to_pdf(svg_path: Path, output_path: Path, dpi: int = 300) -> Path:
    """Convert an SVG file to PDF via cairosvg.

    Args:
        svg_path: Path to an existing SVG file.
        output_path: Destination PDF path.
        dpi: Resolution for any embedded raster bitmaps (default 300).
            Vector geometry is unaffected by dpi.

    Returns:
        Path to the written PDF (== output_path).
    """
    cairosvg.svg2pdf(
        url=str(svg_path),
        write_to=str(output_path),
        dpi=dpi,
        scale=_scale_for_dpi(dpi),
    )
    return output_path
