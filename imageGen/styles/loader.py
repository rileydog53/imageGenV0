"""Journal-style preset loader.

Phase 4. Turns a preset name (e.g. "cell_press", "nature", "acs") into
a flat dict ready to feed into any primitive as `style_dict=…`. Phase 5
renderer will call `load_style(name)` once and thread the result through
every primitive call, flipping a figure's aesthetic with one argument.

Design (locked-in for v1):
  - Presets live as JSON files in this directory; one file per preset,
    name = filename stem.
  - Each preset's `overrides` block is *sparse* — it enumerates only
    the keys it wants to change from primitive `DEFAULT_STYLE`
    defaults. Each primitive already does
    `{**DEFAULT_STYLE, **(style_dict or {})}` so missing keys fall
    back cleanly.
  - `palette` (8 entries) is informational + grep-able. The loader
    does NOT auto-derive primitive fills from palette indices; each
    `*_fill` override is explicit. Palette-to-key auto-derivation is
    flagged in BACKLOG.md as a v2 stretch.
  - `meta` (name + description) is required so a glance at the JSON
    explains what the preset is for.
  - Validation uses the same Pydantic v2 + `extra="forbid"` idiom as
    `ir/schema.py`, keeping the discipline consistent with IR fixtures.

Layout-params (`pathway_canvas`, `panel_margin`, `pathway_seed`, …)
are NOT in the preset — they're geometric/behavioral and caller-set.
A future preset could carry a `layout_overrides` block; flagged in
BACKLOG as deferred.

Phase 5 renderer coupling:
  The renderer calls `load_style(name)` and passes the returned dict
  into every primitive call. Layout engines forward it via their
  existing `style_dict=` kwarg, untouched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


PRESET_DIR = Path(__file__).parent
DEFAULT_PRESET = "cell_press"

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class _PresetMeta(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    description: str


class StylePreset(BaseModel):
    """Validated journal-style preset.

    The `overrides` dict is the payload primitives consume. `meta` and
    `palette` are introspectable via `load_preset_full(name)` for
    callers (e.g. tests, future renderer chrome) that need them.
    """
    model_config = {"extra": "forbid"}

    meta: _PresetMeta
    palette: list[str] = Field(min_length=8, max_length=8)
    overrides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("palette")
    @classmethod
    def _validate_palette_hex(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if not _HEX_COLOR_RE.match(c)]
        if bad:
            raise ValueError(
                f"palette entries must be 7-char #RRGGBB hex; bad entries: {bad!r}"
            )
        return v


def _preset_path(name: str) -> Path:
    return PRESET_DIR / f"{name}.json"


def list_presets() -> list[str]:
    """Discover preset names by listing styles/*.json (sorted)."""
    return sorted(p.stem for p in PRESET_DIR.glob("*.json"))


def load_preset_full(name: str = DEFAULT_PRESET) -> StylePreset:
    """Load + validate a preset; return the typed StylePreset model.

    Useful for tests + future renderer chrome that needs `meta` /
    `palette`. Most callers want `load_style` instead.

    Raises:
        FileNotFoundError: name has no matching JSON in styles/.
        pydantic.ValidationError: schema check failed (missing meta,
            palette wrong length, malformed hex, unknown extra fields).
    """
    path = _preset_path(name)
    if not path.exists():
        available = ", ".join(list_presets()) or "(none)"
        raise FileNotFoundError(
            f"No style preset named {name!r} in {PRESET_DIR}; "
            f"available: {available}"
        )
    return StylePreset.model_validate(json.loads(path.read_text()))


def load_style(name: str = DEFAULT_PRESET) -> dict:
    """Load a journal preset → flat overrides dict for primitives.

    Args:
        name: Preset stem (e.g. "cell_press"). Defaults to cell_press.

    Returns:
        The preset's `overrides` block as a flat dict. Pass directly as
        `style_dict=…` to any primitive; primitive `DEFAULT_STYLE`
        fills any keys the preset omits.

    Raises:
        FileNotFoundError: unknown preset name.
        pydantic.ValidationError: malformed preset JSON.
    """
    return load_preset_full(name).overrides
