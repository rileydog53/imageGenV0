"""Tests for verify/legibility_check.py — Phase 6 Step 2.

Happy-path tests render real fixtures (one per dispatch family) and
assert a ``LegibilityResult`` comes back. Failure modes — overlapping
labels and an undersized font — and the crop signal are exercised with
small hand-written SVG fixtures, which are deterministic and far easier
than coaxing a real render into a known-bad state.
"""
from __future__ import annotations

import pytest

from imageGenV0.render.compositor import render_figure
from imageGenV0.verify.legibility_check import (
    LegibilityCheckError,
    LegibilityResult,
    legibility_check,
)
from tests._helpers import load_fixture

MAPK = "mapk_cascade.json"
OXIDATION = "oxidation_reaction.json"
WORKFLOW = "three_panel_workflow.json"

OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


def _render(fixture, dest, smiles_map=None):
    """Render a fixture to `dest`; return the parsed IR Figure."""
    ir = load_fixture(fixture)
    render_figure(ir, dest, smiles_map=smiles_map)
    return ir


def _write_svg(path, width, height, body):
    """Write a minimal standalone SVG with `body` as its only content."""
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">{body}</svg>'
    )
    return path


def _text(x, y, content, font_size=11):
    """A center-anchored <text> element, matching how the renderer emits labels."""
    return (
        f'<text x="{x}" y="{y}" font-size="{font_size}" '
        f'text-anchor="middle" dominant-baseline="central">{content}</text>'
    )


# ---------------------------------------------------------------------------
# Happy path — one per dispatch family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,smiles",
    [(MAPK, None), (WORKFLOW, None), (OXIDATION, OXIDATION_SMILES)],
)
def test_real_figure_passes(tmp_path, fixture, smiles):
    svg = tmp_path / "fig.svg"
    _render(fixture, svg, smiles_map=smiles)
    result = legibility_check(svg)
    assert isinstance(result, LegibilityResult)
    assert result.canvas_bbox[2] > 0 and result.canvas_bbox[3] > 0


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_overlapping_labels_raise(tmp_path):
    svg = _write_svg(
        tmp_path / "fig.svg", 200, 200,
        _text(100, 100, "Alpha") + _text(104, 100, "Beta"),
    )
    with pytest.raises(LegibilityCheckError) as excinfo:
        legibility_check(svg)
    exc = excinfo.value
    assert exc.kind == "overlap"
    assert set(exc.labels) == {"Alpha", "Beta"}
    assert "overlap" in str(exc)


def test_undersized_font_raises(tmp_path):
    svg = _write_svg(
        tmp_path / "fig.svg", 200, 200,
        _text(100, 100, "Tiny", font_size=3),
    )
    with pytest.raises(LegibilityCheckError) as excinfo:
        legibility_check(svg)
    exc = excinfo.value
    assert exc.kind == "font_size"
    assert exc.labels == ("Tiny",)
    assert "Tiny" in str(exc)


def test_undersized_font_threshold_is_configurable(tmp_path):
    """An 8pt label passes by default but fails a stricter floor."""
    svg = _write_svg(tmp_path / "fig.svg", 200, 200, _text(100, 100, "Mid", font_size=8))
    legibility_check(svg)  # 8 >= default 6.0 — no raise
    with pytest.raises(LegibilityCheckError):
        legibility_check(svg, min_font_size=10.0)


# ---------------------------------------------------------------------------
# Crop signal
# ---------------------------------------------------------------------------


def test_sparse_content_needs_crop(tmp_path):
    """A small label alone on a large canvas leaves excess whitespace."""
    svg = _write_svg(tmp_path / "fig.svg", 1000, 1000, _text(60, 60, "Lonely"))
    result = legibility_check(svg)
    assert result.needs_crop is True
    assert result.canvas_bbox == (0.0, 0.0, 1000.0, 1000.0)


def test_dense_content_no_crop(tmp_path):
    """Content (a rect) filling the canvas leaves no croppable whitespace."""
    svg = _write_svg(
        tmp_path / "fig.svg", 200, 200,
        '<rect x="0" y="0" width="200" height="200" />' + _text(100, 100, "Full"),
    )
    result = legibility_check(svg)
    assert result.needs_crop is False
    assert result.content_bbox == (0.0, 0.0, 200.0, 200.0)
