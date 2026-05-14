"""Shared types for the layout package.

This module exists so that downstream layout engines and external callers
can import a single, stable name for the layout-output record without
reaching into any one engine's private namespace.
"""
from __future__ import annotations

from typing import Any, Callable, NamedTuple

import svgwrite.container


class LayoutEntry(NamedTuple):
    """One unit of work for the renderer: a primitive call + its position.

    ir_id: raw IR id for tagging the emitted SVG element (D1). None for
    synthetic chrome (panel borders, etc.) that has no IR counterpart.

    panel_chain: panel-hierarchy prefix for SVG-id scoping (D1). Non-empty
    only when the entry was emitted inside a `layout_panel` sub-engine
    call; the compositor combines it with `ir_id` to produce document-
    unique SVG ids like `p1__ras` while keeping `data-ir-id="ras"`.
    """
    primitive: Callable[..., svgwrite.container.Group]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    position: tuple[float, float]
    ir_id: str | None = None
    panel_chain: tuple[str, ...] = ()
