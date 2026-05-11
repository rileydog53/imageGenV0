"""Phase 2 tests for primitives/arrows.py.

Each public function gets a type-check test. A final render test converts every
arrow type to PNG (via cairosvg) and writes the files to tests/figures/ — these
become the golden-image seeds for Phase 6 regression testing.
"""
from __future__ import annotations

import svgwrite
import svgwrite.container

from primitives.arrows import (
    activation_arrow,
    binding_arrow,
    inhibition_arrow,
    reaction_arrow,
    translocation_arrow,
)
from tests._helpers import render_group_to_png

START = (20.0, 60.0)
END = (180.0, 60.0)


# ---------------------------------------------------------------------------
# Type-check tests — each arrow function must return a Group
# ---------------------------------------------------------------------------

def test_activation_arrow_returns_group():
    """activation_arrow (straight) returns a svgwrite Group."""
    g = activation_arrow(START, END)
    assert isinstance(g, svgwrite.container.Group)


def test_activation_arrow_curved_returns_group():
    """activation_arrow (curved=True) returns a svgwrite Group."""
    g = activation_arrow(START, END, curved=True)
    assert isinstance(g, svgwrite.container.Group)


def test_inhibition_arrow_returns_group():
    """inhibition_arrow returns a svgwrite Group with a T-bar, not an arrowhead."""
    g = inhibition_arrow(START, END)
    assert isinstance(g, svgwrite.container.Group)


def test_binding_arrow_returns_group():
    """binding_arrow (bidirectional) returns a svgwrite Group."""
    g = binding_arrow(START, END)
    assert isinstance(g, svgwrite.container.Group)


def test_translocation_arrow_returns_group():
    """translocation_arrow (dashed + open head) returns a svgwrite Group."""
    g = translocation_arrow(START, END)
    assert isinstance(g, svgwrite.container.Group)


def test_reaction_arrow_with_all_options():
    """reaction_arrow with conditions, reagents, yield_pct, and reversible=True."""
    g = reaction_arrow(
        START,
        END,
        conditions="heat",
        reagents="NaCl",
        yield_pct=85.0,
        reversible=True,
    )
    assert isinstance(g, svgwrite.container.Group)


# ---------------------------------------------------------------------------
# Render-to-PNG test — produces golden-image seeds for Phase 6
# ---------------------------------------------------------------------------

def test_arrows_render_to_png():
    """Render one PNG per arrow type; assert each file exists and is non-empty."""
    cases = {
        "arrow_activation.png": activation_arrow(START, END),
        "arrow_activation_curved.png": activation_arrow(START, END, curved=True),
        "arrow_inhibition.png": inhibition_arrow(START, END),
        "arrow_binding.png": binding_arrow(START, END),
        "arrow_translocation.png": translocation_arrow(START, END),
        "arrow_reaction.png": reaction_arrow(
            START,
            END,
            conditions="heat",
            yield_pct=85.0,
            reversible=True,
        ),
    }
    for filename, group in cases.items():
        out = render_group_to_png(group, filename, canvas=(200, 120))
        assert out.exists(), f"PNG not written: {out}"
        assert out.stat().st_size > 100, f"PNG suspiciously small: {out}"
