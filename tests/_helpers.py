"""Shared test helpers.

Three module-level helpers used across the suite:

- ``load_fixture(name)`` — parse ``tests/fixtures/<name>`` as a ``Figure``.
- ``render_entries_to_png(entries, filename, canvas)`` — compose a list of
  ``LayoutEntry`` instances into an SVG and write a PNG to ``tests/figures/``.
- ``render_group_to_png(group, filename, canvas)`` — wrap a single svgwrite
  ``Group`` in a white-background drawing and write a PNG to ``tests/figures/``.

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
import svgwrite
import svgwrite.container

from ir.schema import Figure
from layout.reaction_layout import LayoutEntry

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
