"""Shared test helpers.

Three module-level helpers used across the suite:

- ``load_fixture(name)`` — parse ``tests/fixtures/<name>`` as a ``Figure``.
- ``render_entries_to_png(entries, filename, canvas)`` — compose a list of
  ``LayoutEntry`` instances into an SVG and write a PNG to ``tests/figures/``.
- ``render_group_to_png(group, filename, canvas)`` — wrap a single svgwrite
  ``Group`` in a white-background drawing and write a PNG to ``tests/figures/``.
- ``compare_pngs(path_a, path_b, channel_tol)`` — pixel-diff two PNGs; the
  Phase 6 golden-image regression suite uses it to detect visual drift.

The two render helpers exist because layout-engine tests produce
``list[LayoutEntry]`` (with per-entry ``position`` offsets) while primitive
tests produce a single pre-positioned ``Group``. Keeping them as separate
functions avoids a leaky union return shape.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import cairosvg
import numpy as np
import svgwrite
import svgwrite.container
from PIL import Image

from imageGen.ir.schema import Figure
from imageGen.layout.types import LayoutEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIGURES_DIR = Path(__file__).parent / "figures"


def load_fixture(name: str) -> Figure:
    """Load and validate a JSON IR fixture from ``tests/fixtures/``."""
    return Figure.model_validate(json.loads((FIXTURES_DIR / name).read_text()))


def render_entries_to_png(
    entries: Iterable[LayoutEntry],
    filename: str,
    canvas: tuple[int, int] = (800, 600),
) -> Path:
    """Render a list of ``LayoutEntry`` into a PNG at ``tests/figures/<filename>``.

    Each entry's primitive is invoked with its args/kwargs and translated by
    the entry's ``position``. A white background is drawn first so the PNG is
    human-readable.
    """
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


def render_group_to_png(
    group: svgwrite.container.Group,
    filename: str,
    canvas: tuple[int, int] = (400, 200),
) -> Path:
    """Render a single svgwrite ``Group`` into a PNG at ``tests/figures/<filename>``."""
    w, h = canvas
    dwg = svgwrite.Drawing(size=(f"{w}px", f"{h}px"))
    dwg.add(dwg.rect(insert=(0, 0), size=(f"{w}px", f"{h}px"), fill="white"))
    dwg.add(group)
    FIGURES_DIR.mkdir(exist_ok=True)
    out = FIGURES_DIR / filename
    out.write_bytes(cairosvg.svg2png(bytestring=dwg.tostring().encode("utf-8")))
    return out


def compare_pngs(
    path_a: Path | str,
    path_b: Path | str,
    *,
    channel_tol: int = 8,
) -> float:
    """Pixel-diff two PNGs and return the fraction of differing pixels.

    A pixel counts as differing when any RGBA channel's absolute difference
    exceeds ``channel_tol`` — the slack absorbs minor cairo/font antialiasing
    variance so the golden suite flags real regressions, not render noise.

    Args:
        path_a: First PNG path.
        path_b: Second PNG path.
        channel_tol: Per-channel absolute-difference threshold (0–255).

    Returns:
        Fraction of differing pixels, a float in [0.0, 1.0].

    Raises:
        ValueError: If the two images have different dimensions.
    """
    img_a = Image.open(path_a).convert("RGBA")
    img_b = Image.open(path_b).convert("RGBA")
    if img_a.size != img_b.size:
        raise ValueError(
            f"Image dimensions differ: {path_a} is {img_a.size}, "
            f"{path_b} is {img_b.size}."
        )
    # int16 so per-channel subtraction does not underflow uint8.
    diff = np.abs(np.array(img_a, dtype=np.int16) - np.array(img_b, dtype=np.int16))
    pixel_differs = np.any(diff > channel_tol, axis=2)
    return float(np.sum(pixel_differs) / pixel_differs.size)
