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
    """
    primitive: Callable[..., svgwrite.container.Group]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    position: tuple[float, float]
    ir_id: str | None = None
