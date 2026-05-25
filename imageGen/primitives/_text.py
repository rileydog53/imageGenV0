"""Shared text-rendering helpers for primitive modules.

Promoted from ``proteins._centered_label`` (V2 / P3) so any primitive
module — and layout helpers such as ``label_placement`` — can build
centered text labels without coupling to ``proteins.py``.

The function is intentionally minimal: it wraps svgwrite's Text element
with the three standard centering attributes and honours the master-preset
``label_*`` style keys. All label styling in the codebase flows through
this single entry point so a preset change propagates everywhere.
"""
from __future__ import annotations

from typing import Optional

import svgwrite.text


def centered_label(
    text: str,
    cx: float,
    cy: float,
    style: dict,
    *,
    weight: str = "normal",
    color: Optional[str] = None,
    size_override: Optional[float] = None,
) -> svgwrite.text.Text:
    """Build a horizontally + vertically centered SVG text element.

    Args:
        text:          The string to render.
        cx, cy:        Centre-point of the text element.
        style:         Merged style dict; must contain ``label_font_family``,
                       ``label_font_size``, and ``label_font_color``.
        weight:        CSS ``font-weight`` value; omitted when ``"normal"``.
        color:         Fill color override; defaults to ``style["label_font_color"]``.
        size_override: Font-size override in px; defaults to ``style["label_font_size"]``.

    Returns:
        An ``svgwrite.text.Text`` with ``text-anchor: middle`` and
        ``dominant-baseline: central`` so callers only need to supply the
        centre-point — no manual offset arithmetic required.
    """
    t = svgwrite.text.Text(
        text,
        insert=(cx, cy),
        font_family=style["label_font_family"],
        font_size=float(size_override or style["label_font_size"]),
        fill=color or style["label_font_color"],
    )
    t["text-anchor"] = "middle"
    t["dominant-baseline"] = "central"
    if weight != "normal":
        t["font-weight"] = weight
    return t
