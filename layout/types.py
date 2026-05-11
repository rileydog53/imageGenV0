"""Shared types for the layout package.

This module exists so that downstream layout engines and external callers
can import a single, stable name for the layout-output record without
reaching into any one engine's private namespace.
"""
from __future__ import annotations

from typing import Any, Callable, NamedTuple

import svgwrite.container


class LayoutEntry(NamedTuple):
    """One unit of work for the renderer: a primitive call + its position."""
    primitive: Callable[..., svgwrite.container.Group]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    position: tuple[float, float]
