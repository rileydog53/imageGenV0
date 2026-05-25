"""Renderer & compositor — Phase 5.

Orchestrates the full pipeline from a validated IR `Figure` to a final
SVG/PNG/PDF file on disk.

Pipeline per call to `render_figure`:
  1. Resolve style preset (`style_name` kwarg overrides `ir.style_preset`;
     falls back to DEFAULT_PRESET from `styles/loader.py`).
  2. Dispatch IR archetype → layout engine → list[LayoutEntry].
  3. Auto-invoke label placement if the dispatched engine has a sibling
     `*_label_requests` helper and `labels=True` (D3).
  4. Inject a demonstrative-data watermark if `_needs_watermark` returns
     True — stub for v1 (D2).
  5. Compose into a single `svgwrite.Drawing` with IR-id tagging (D1)
     and write to disk.
  6. For non-SVG formats, convert the on-disk SVG into PNG/PDF via
     `render/export.py`. The SVG is persisted at
     `output_path.with_suffix(".svg")` next to the requested output so
     callers can inspect / debug it.

Archetype dispatch (v1 scope):
  - Multi-panel (`ir.panels` populated) → `layout_panel`; labels run
    per-panel via `_place_labels_per_panel`. The flat `smiles_map` is
    broadcast to all panels (entity ids are unique by IR validation).
  - PATHWAY → `layout_pathway`; siblings: `pathway_label_requests`
  - REACTION_SCHEME → `layout_reaction`; requires `smiles_map` kwarg (D4).
    No label-request sibling — labels are baked into render_reaction.
  - All other leaf archetypes raise `NotImplementedError`.

IR-id tagging (D1):
  Every emitted `<g>` carries:
  - `data-ir-id="<raw-ir-id>"` — always; used by Phase 6 semantic_check.
  - `id="<scoped-id>"` — panel-chain prefix for document uniqueness.
    At depth 0 (no panel): scoped-id == raw-ir-id.

Step coupling:
  - Step 2 (done): REACTION_SCHEME + smiles_map dispatch.
  - Step 3 (done): PANEL dispatch — panel-keyed `_dispatch_layout`
    branch, per-panel `_place_labels_per_panel`, per-entry panel_chain
    SVG-id scoping.
  - Step 4 (done): `render/export.py` wired in below; format != "svg"
    writes a sibling SVG then converts via cairosvg.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Literal

import svgwrite

from imageGen.ir.schema import Archetype, Figure
from imageGen.layout.label_placement import LabelPlacementError, place_labels
from imageGen.layout.panel_layout import (
    PANEL_DEFAULT_PARAMS,
    layout_panel,
)
from imageGen.layout._geom import entities_per_band, max_entity_bbox  # retained for tests that import via this module
from imageGen.layout.pathway_layout import (
    PATHWAY_DEFAULT_PARAMS,
    _PATHWAY_COMPATIBLE_ARCHETYPES,
    compute_pathway_canvas,
    layout_pathway,
    pathway_label_requests,
)
from imageGen.layout.reaction_layout import (
    REACTION_DEFAULT_PARAMS,
    layout_reaction,
    reaction_label_requests,
)
from imageGen.layout.types import LayoutEntry
from imageGen.render.export import svg_to_pdf, svg_to_png
from imageGen.styles.loader import DEFAULT_PRESET, load_style

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CANVAS = (800.0, 600.0)

Format = Literal["svg", "png", "pdf"]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_figure(
    ir: Figure,
    output_path: str | Path,
    *,
    style_name: str | None = None,
    format: Format | None = None,
    smiles_map: dict[str, str] | None = None,
    labels: bool = True,
    dpi: int = 300,
    display_dpi: int | None = None,
    canvas: tuple[float, float] | None = None,
    strict_labels: bool = False,
) -> Path:
    """Render an IR Figure to a file and return the resolved output Path.

    Args:
        ir: Validated IR Figure (from `ir.schema`).
        output_path: Destination file path. Format is inferred from the
            suffix when `format` is None.
        style_name: Journal preset name (e.g., "nature"). Overrides
            `ir.style_preset`. Defaults to DEFAULT_PRESET when both
            are absent.
        format: Output format ("svg", "png", or "pdf"). None means infer
            from `output_path` suffix.
        smiles_map: {entity_id: SMILES string} for REACTION_SCHEME
            figures (required by `layout_reaction`).
        labels: When True (default), auto-invoke label placement if the
            dispatched layout engine has a sibling `*_label_requests`
            helper (D3). Pass False to suppress labels (debugging).
        dpi: Output resolution (default 300, journal quality). Forwarded
            to cairosvg for both PNG and PDF; PDFs use it only for any
            embedded raster bitmaps. Ignored when format == "svg".
        display_dpi: When set (e.g. 96), also writes a low-resolution
            screen copy at ``<stem>_display.png`` next to the deliverable.
            Never overwrites the main output. Ignored when format != "png".

    Returns:
        Resolved Path to the written file. For non-SVG formats a sibling
        SVG is also written at `output_path.with_suffix(".svg")`.

    Raises:
        NotImplementedError: For archetypes not yet wired in the
            compositor.
        ValueError: For unrecognised file suffix when `format` is None.
        LabelPlacementError: Propagated from `place_labels` when a label
            cannot be placed at any candidate position.
    """
    output_path = Path(output_path)
    fmt = _resolve_format(output_path, format)
    style_dict = _resolve_style(ir, style_name)
    entries = _dispatch_layout(ir, style_dict, smiles_map)

    # L18: compute canvas before label placement so the bounds can be forwarded
    # to place_labels, preventing labels from rendering outside the SVG viewport.
    computed_canvas = _canvas_size(ir, entries)

    if labels:
        if ir.panels:
            entries = _place_labels_per_panel(
                ir, entries, style_dict, strict_labels=strict_labels,
                canvas=computed_canvas,
            )
        else:
            label_fn = _label_requests_fn(ir.archetype)
            if label_fn is not None:
                requests = label_fn(ir, entries)
                entries = place_labels(
                    entries, requests, style_dict=style_dict,
                    canvas=computed_canvas,
                    strict_labels=strict_labels,
                )

    if _needs_watermark(ir):
        entries = _inject_watermark(entries, ir, style_dict)

    final_canvas = canvas if canvas is not None else computed_canvas
    svg_path = output_path if fmt == "svg" else output_path.with_suffix(".svg")
    _write_svg(entries, final_canvas, svg_path)
    if fmt == "png":
        svg_to_png(svg_path, output_path, dpi=dpi)
        if display_dpi is not None:
            display_path = output_path.with_stem(output_path.stem + "_display")
            svg_to_png(svg_path, display_path, dpi=display_dpi)
    elif fmt == "pdf":
        svg_to_pdf(svg_path, output_path, dpi=dpi)
    return output_path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_style(ir: Figure, style_name: str | None) -> dict[str, Any]:
    """Return the style overrides dict, preferring kwarg > ir.style_preset > default."""
    name = style_name or ir.style_preset or DEFAULT_PRESET
    return load_style(name)


def _resolve_format(
    output_path: Path, format: Format | None
) -> Format:
    if format is not None:
        return format
    suffix = output_path.suffix.lstrip(".")
    if suffix not in {"svg", "png", "pdf"}:
        raise ValueError(
            f"Cannot infer output format from suffix {output_path.suffix!r}; "
            "pass format= explicitly or use .svg / .png / .pdf"
        )
    return suffix  # type: ignore[return-value]


def _dispatch_layout(
    ir: Figure,
    style_dict: dict[str, Any],
    smiles_map: dict[str, str] | None,
) -> list[LayoutEntry]:
    """Call the appropriate layout engine for the IR shape.

    Multi-panel figures (`ir.panels` populated) dispatch to
    `layout_panel` regardless of top-level archetype. Leaf figures
    dispatch on `ir.archetype`: every pathway-compatible archetype
    (PATHWAY, WORKFLOW, CELLULAR_SCHEMATIC, MECHANISM_CARTOON) →
    layout_pathway, REACTION_SCHEME → layout_reaction. The trailing
    NotImplementedError guards any future archetype enum addition.

    The flat `smiles_map: {entity_id: SMILES}` is adapted to the nested
    `{panel.id: smiles_map}` shape that `layout_panel` expects — entity
    ids are unique across the figure (IR validates), so broadcasting
    the same dict to every panel is safe.
    """
    if ir.panels:
        smiles_maps = (
            {p.id: smiles_map for p in ir.panels} if smiles_map else None
        )
        return layout_panel(ir, smiles_maps=smiles_maps, style_dict=style_dict)
    if ir.archetype in _PATHWAY_COMPATIBLE_ARCHETYPES:
        return layout_pathway(ir, style_dict=style_dict)
    if ir.archetype == Archetype.REACTION_SCHEME:
        if smiles_map is None:
            missing = [e.id for e in ir.entities]
            raise ValueError(
                f"smiles_map required for REACTION_SCHEME; "
                f"missing entity ids: {missing}"
            )
        return layout_reaction(ir, smiles_map=smiles_map, style_dict=style_dict)
    raise NotImplementedError(
        f"Archetype {ir.archetype!r} is not yet wired in the compositor "
        "(and the figure has no panels)."
    )


def _place_labels_per_panel(
    ir: Figure,
    entries: list[LayoutEntry],
    style_dict: dict[str, Any],
    *,
    strict_labels: bool = False,
    canvas: tuple[float, float] | None = None,
) -> list[LayoutEntry]:
    """Run label placement separately for each panel's slice of entries.

    Buckets entries by `entry.panel_chain[0]` (chrome lives in the
    empty-chain bucket and passes through untouched). For each panel
    whose content archetype has a `*_label_requests` sibling, requests
    are computed from that panel's content + entries, labels are placed
    using only that bucket (collision-isolated), and each newly-placed
    label entry is re-stamped with `panel_chain=(panel.id,)` and the
    panel's render offset so it lands inside its cell.

    Sub-engines lay out in (0, 0)-origin panel-local coordinates and
    rely on a per-entry `position` to translate the rendered group into
    the parent canvas. `pathway_label_requests` reads `arrow.args`
    (local coords), so labels come back in panel-local coords with
    `position=(0, 0)` — they would otherwise render at the same
    absolute spot in every panel. The panel offset is shared across all
    sub-entries (set by `_shift_entry` in `layout_panel`), so we read it
    from any bucket entry.
    """
    buckets: dict[str | None, list[LayoutEntry]] = {None: []}
    for entry in entries:
        key = entry.panel_chain[0] if entry.panel_chain else None
        buckets.setdefault(key, []).append(entry)

    result: list[LayoutEntry] = list(buckets[None])
    for panel in ir.panels:
        bucket = buckets.get(panel.id, [])
        label_fn = _label_requests_fn(panel.content.archetype)
        if label_fn is None or not bucket:
            result.extend(bucket)
            continue
        panel_offset = bucket[0].position  # shared by every sub-entry
        requests = label_fn(panel.content, bucket)
        placed = place_labels(
            bucket, requests, style_dict=style_dict,
            canvas=canvas, strict_labels=strict_labels,
        )
        result.extend(placed[:len(bucket)])
        for label_entry in placed[len(bucket):]:
            result.append(label_entry._replace(
                panel_chain=(panel.id,),
                position=panel_offset,
            ))
    return result


def _label_requests_fn(archetype: Archetype) -> Any | None:
    """Return the *_label_requests sibling for the given archetype, or None.

    Implements D3: the compositor discovers label-request helpers by
    archetype, rather than each layout engine auto-invoking placement.
    Returns None when no helper exists (reaction layouts in v1).

    Pathway-family archetypes (PATHWAY / WORKFLOW / CELLULAR_SCHEMATIC /
    MECHANISM_CARTOON) all dispatch through `layout_pathway` and share
    `pathway_label_requests`.
    """
    if archetype in _PATHWAY_COMPATIBLE_ARCHETYPES:
        return pathway_label_requests
    if archetype == Archetype.REACTION_SCHEME:
        return reaction_label_requests
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
    # Reached only when _needs_watermark returns True — always False in v1.
    raise NotImplementedError("Watermark injection not yet implemented.")


def _canvas_size(ir: Figure, entries: list[LayoutEntry]) -> tuple[float, float]:
    """Return (width, height) of the SVG viewport.

    Pathway-family figures get a content-aware canvas (see
    `_compute_pathway_canvas`) clamped to the v1 default `(800, 600)` so
    small figures stay golden-image-identical. Panels and reactions still
    use their respective static defaults — those engines lay out within a
    fixed envelope already.
    """
    if ir.panels:
        return PANEL_DEFAULT_PARAMS["panel_canvas"]
    if ir.archetype in _PATHWAY_COMPATIBLE_ARCHETYPES:
        return _compute_pathway_canvas(ir)
    if ir.archetype == Archetype.REACTION_SCHEME:
        return REACTION_DEFAULT_PARAMS["reaction_canvas"]
    return _DEFAULT_CANVAS


def _compute_pathway_canvas(figure: Figure) -> tuple[float, float]:
    """Content-aware canvas for pathway-family figures.

    V2: delegates to ``pathway_layout.compute_pathway_canvas`` so the
    formula is defined in one place and both the compositor (SVG viewport)
    and ``layout_pathway`` (band geometry) agree on the canvas size.

    Kept as a private function here so existing tests that import it from
    this module continue to work unchanged.
    """
    return compute_pathway_canvas(figure)


def scoped_id(raw_ir_id: str, panel_chain: tuple[str, ...]) -> str:
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
    group.attribs["id"] = scoped_id(raw_ir_id, panel_chain)
    group.attribs["data-ir-id"] = raw_ir_id


def _write_svg(
    entries: list[LayoutEntry],
    canvas: tuple[float, float],
    output_path: Path,
) -> None:
    """Execute layout entries into an svgwrite Drawing and write to disk.

    Per-entry `panel_chain` (set by `layout_panel`) drives SVG-id
    scoping; non-panel figures leave it as () and scoped id == raw id.
    """
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
            _tag_group(group, entry.ir_id, entry.panel_chain)
        dwg.add(group)

    dwg.save()
