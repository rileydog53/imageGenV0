"""Renderer & compositor — Phase 5.

Orchestrates the full pipeline from a validated IR `Figure` to a final
SVG file (PNG/PDF added in Step 4 via `render/export.py`).

Pipeline per call to `render_figure`:
  1. Resolve style preset (`style_name` kwarg overrides `ir.style_preset`;
     falls back to DEFAULT_PRESET from `styles/loader.py`).
  2. Dispatch IR archetype → layout engine → list[LayoutEntry].
  3. Auto-invoke label placement if the dispatched engine has a sibling
     `*_label_requests` helper and `labels=True` (D3).
  4. Inject a demonstrative-data watermark if `_needs_watermark` returns
     True — stub for v1 (D2).
  5. Compose into a single `svgwrite.Drawing` with IR-id tagging (D1)
     and write to `output_path`.

Archetype dispatch (v1 scope):
  - PATHWAY → `layout_pathway`; siblings: `pathway_label_requests`
  - REACTION_SCHEME → `layout_reaction`; requires `smiles_map` kwarg (D4).
    No label-request sibling — labels are baked into render_reaction.
  - All others raise `NotImplementedError` until subsequent steps wire them.

IR-id tagging (D1):
  Every emitted `<g>` carries:
  - `data-ir-id="<raw-ir-id>"` — always; used by Phase 6 semantic_check.
  - `id="<scoped-id>"` — panel-chain prefix for document uniqueness.
    At depth 0 (no panel): scoped-id == raw-ir-id.

Step coupling:
  - Step 2 (done): REACTION_SCHEME + smiles_map dispatch.
  - Step 3 extends `_dispatch_layout` for PANEL (recursive sub-figure calls).
  - Step 4 adds `render/export.py` and wires format != "svg" here.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Literal

import svgwrite

from ir.schema import Archetype, Figure
from layout.label_placement import LabelPlacementError, place_labels
from layout.pathway_layout import layout_pathway, pathway_label_requests
from layout.types import LayoutEntry
from styles.loader import DEFAULT_PRESET, load_style

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PATHWAY_CANVAS_PARAM = "pathway_canvas"
_DEFAULT_CANVAS = (800.0, 600.0)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_figure(
    ir: Figure,
    output_path: str | Path,
    *,
    style_name: str | None = None,
    format: Literal["svg", "png", "pdf"] | None = None,
    smiles_map: dict[str, str] | None = None,
    labels: bool = True,
    dpi: int = 300,
) -> Path:
    """Render an IR Figure to a file and return the resolved output Path.

    Args:
        ir: Validated IR Figure (from `ir.schema`).
        output_path: Destination file path. Format is inferred from the
            suffix when `format` is None.
        style_name: Journal preset name (e.g., "nature"). Overrides
            `ir.style_preset`. Defaults to DEFAULT_PRESET when both
            are absent.
        format: Output format. None means infer from `output_path` suffix.
            Step 1 supports "svg" only; "png" and "pdf" raise
            NotImplementedError until Step 4.
        smiles_map: {entity_id: SMILES string} for REACTION_SCHEME
            figures. Unused in Step 1; forwarded in Step 2.
        labels: When True (default), auto-invoke label placement if the
            dispatched layout engine has a sibling `*_label_requests`
            helper (D3). Pass False to suppress labels (debugging).
        dpi: Output resolution for raster formats (Step 4+). Ignored in
            Step 1.

    Returns:
        Resolved Path to the written file.

    Raises:
        NotImplementedError: For archetypes not yet wired (Step 1:
            non-PATHWAY) or formats not yet supported (Step 1: non-svg).
        ValueError: For unrecognised file suffix when `format` is None.
        LabelPlacementError: Propagated from `place_labels` when a label
            cannot be placed at any candidate position.
    """
    output_path = Path(output_path)
    fmt = _resolve_format(output_path, format)
    style_dict = _resolve_style(ir, style_name)
    entries = _dispatch_layout(ir, style_dict, smiles_map)

    if labels:
        label_fn = _label_requests_fn(ir.archetype)
        if label_fn is not None:
            requests = label_fn(ir, entries)
            entries = place_labels(entries, requests, style_dict=style_dict)

    if _needs_watermark(ir):
        entries = _inject_watermark(entries, ir, style_dict)

    canvas = _canvas_size(ir, entries)
    _write_svg(entries, canvas, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_style(ir: Figure, style_name: str | None) -> dict[str, Any]:
    """Return the style overrides dict, preferring kwarg > ir.style_preset > default."""
    name = style_name or ir.style_preset or DEFAULT_PRESET
    return load_style(name)


def _resolve_format(
    output_path: Path, format: Literal["svg", "png", "pdf"] | None
) -> str:
    if format is not None:
        resolved = format
    else:
        suffix = output_path.suffix.lstrip(".")
        if suffix not in {"svg", "png", "pdf"}:
            raise ValueError(
                f"Cannot infer output format from suffix {output_path.suffix!r}; "
                "pass format= explicitly or use .svg / .png / .pdf"
            )
        resolved = suffix
    if resolved in {"png", "pdf"}:
        raise NotImplementedError(
            f"Format {resolved!r} is not yet supported in Phase 5 Step 1; "
            "it will be wired in Step 4 via render/export.py"
        )
    return resolved


def _dispatch_layout(
    ir: Figure,
    style_dict: dict[str, Any],
    smiles_map: dict[str, str] | None,
) -> list[LayoutEntry]:
    """Call the appropriate layout engine for `ir.archetype`.

    Step 1: PATHWAY only. Remaining archetypes raise NotImplementedError
    with a note on which step wires them.
    """
    if ir.archetype == Archetype.PATHWAY:
        return layout_pathway(ir, style_dict=style_dict)
    raise NotImplementedError(
        f"Archetype {ir.archetype!r} is not yet wired in the compositor. "
        "REACTION_SCHEME is added in Step 2; PANEL dispatch in Step 3."
    )


def _label_requests_fn(archetype: Archetype):
    """Return the *_label_requests sibling for the given archetype, or None.

    Implements D3: the compositor discovers label-request helpers by
    archetype, rather than each layout engine auto-invoking placement.
    Returns None when no helper exists (reaction layouts in v1, panels).
    """
    if archetype == Archetype.PATHWAY:
        return pathway_label_requests
    return None


def _needs_watermark(ir: Figure) -> bool:
    """Return True when the figure requires a demonstrative-data watermark.

    Stub for v1 (D2): no current archetype is chart-like, so this always
    returns False. Replace with a real check when a CHART archetype or
    quantitative-value field is added to the IR.
    """
    # TODO: trigger when Archetype.CHART is added or entity gains quantitative_value
    return False


def _inject_watermark(
    entries: list[LayoutEntry], ir: Figure, style_dict: dict[str, Any]
) -> list[LayoutEntry]:
    """Append a demonstrative-data watermark entry (placeholder, never reached in v1)."""
    # Reached only when _needs_watermark returns True — not possible in Step 1.
    raise NotImplementedError("Watermark injection not yet implemented.")


def _canvas_size(ir: Figure, entries: list[LayoutEntry]) -> tuple[float, float]:
    """Return (width, height) of the SVG viewport.

    Uses pathway_canvas from DEFAULT_LAYOUT_PARAMS for PATHWAY figures.
    Future steps can inspect entries or pass layout params through instead.
    """
    if ir.archetype == Archetype.PATHWAY:
        from layout.pathway_layout import DEFAULT_LAYOUT_PARAMS
        return DEFAULT_LAYOUT_PARAMS[_PATHWAY_CANVAS_PARAM]
    return _DEFAULT_CANVAS


def _scoped_id(raw_ir_id: str, panel_chain: tuple[str, ...]) -> str:
    """Build a document-unique SVG id from the panel hierarchy prefix + raw id (D1)."""
    if panel_chain:
        return "__".join((*panel_chain, raw_ir_id))
    return raw_ir_id


def _tag_group(
    group: svgwrite.container.Group,
    raw_ir_id: str,
    panel_chain: tuple[str, ...] = (),
) -> None:
    """Set id (scoped) and data-ir-id (raw) on a Group in-place (D1).

    Disables debug-mode validation on the group before writing so that
    data-* attributes (valid SVG 1.1 / HTML5 custom attributes) are not
    rejected by svgwrite's strict built-in allowlist. The group's
    children are unaffected — each element carries its own debug flag.
    """
    group._parameter.debug = False  # allow data-* attrs; debug is a read-only property
    group.attribs["id"] = _scoped_id(raw_ir_id, panel_chain)
    group.attribs["data-ir-id"] = raw_ir_id


def _write_svg(
    entries: list[LayoutEntry],
    canvas: tuple[float, float],
    output_path: Path,
    panel_chain: tuple[str, ...] = (),
) -> None:
    """Execute layout entries into an svgwrite Drawing and write to disk."""
    w, h = canvas
    # debug=False disables svgwrite's strict SVG attribute validation so we
    # can emit data-* attributes (data-ir-id) which are valid SVG 1.1/HTML5
    # but not in svgwrite's built-in allowlist.
    dwg = svgwrite.Drawing(str(output_path), size=(w, h), debug=False)

    for entry in entries:
        group: svgwrite.container.Group = entry.primitive(*entry.args, **entry.kwargs)
        px, py = entry.position
        if px != 0.0 or py != 0.0:
            group["transform"] = f"translate({px},{py})"
        if entry.ir_id is not None:
            _tag_group(group, entry.ir_id, panel_chain)
        dwg.add(group)

    dwg.save()
