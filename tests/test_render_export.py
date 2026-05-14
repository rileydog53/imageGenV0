"""Tests for render/export.py — Phase 5 Step 4.

Covers svg_to_png and svg_to_pdf, the thin cairosvg wrappers used by
`render_figure` for non-SVG output formats.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from render.export import svg_to_pdf, svg_to_png

_MIN_SVG = (
    b'<?xml version="1.0"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60">'
    b'<rect x="10" y="10" width="80" height="40" fill="red"/>'
    b"</svg>"
)


def _write_min_svg(path: Path) -> Path:
    path.write_bytes(_MIN_SVG)
    return path


def test_svg_to_png_writes_file(tmp_path):
    src = _write_min_svg(tmp_path / "in.svg")
    out = svg_to_png(src, tmp_path / "out.png")
    assert out == tmp_path / "out.png"
    assert out.exists()
    assert out.stat().st_size > 0


def test_svg_to_png_is_readable_by_pillow(tmp_path):
    src = _write_min_svg(tmp_path / "in.svg")
    out = svg_to_png(src, tmp_path / "out.png")
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.width > 0 and img.height > 0


def test_svg_to_png_higher_dpi_yields_larger_image(tmp_path):
    """Pixel dimensions scale with dpi — proves the kwarg is forwarded."""
    src = _write_min_svg(tmp_path / "in.svg")
    lo = svg_to_png(src, tmp_path / "lo.png", dpi=96)
    hi = svg_to_png(src, tmp_path / "hi.png", dpi=300)
    with Image.open(lo) as a, Image.open(hi) as b:
        assert b.width > a.width
        assert b.height > a.height


def test_svg_to_pdf_writes_pdf_file(tmp_path):
    src = _write_min_svg(tmp_path / "in.svg")
    out = svg_to_pdf(src, tmp_path / "out.pdf")
    assert out == tmp_path / "out.pdf"
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
