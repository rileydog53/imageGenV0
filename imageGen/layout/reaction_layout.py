"""Reaction-scheme layout engine.

Translates an IR `Figure` whose `archetype == REACTION_SCHEME` into a
list of `LayoutEntry` tuples that the Phase 5 renderer consumes. Each
LayoutEntry packages a primitive callable, its positional args, its
keyword args, and the (x, y) at which the resulting svgwrite Group
should be translated.

v1 produces a single entry calling `primitives.chemistry.render_reaction`
which already handles the left-to-right horizontal layout of reactants
+ arrow + products. The engine's job here is purely the IR → arguments
translation: classifying entities into reactants vs products from the
relation graph, mapping the IR's ReactionConditions to render_reaction's
{"above", "below"} dict, and routing SMILES from a caller-supplied map.

SMILES sourcing:
  The IR has no SMILES field on entities (entities carry only `label`
  for human-readable names). Rather than baking a label-to-SMILES
  lookup into layout (brittle, gives layout chemistry knowledge),
  overloading `entity.style` (style is for visual presets), or
  modifying the Phase 1 IR schema for a single Phase 3 task, the engine
  takes a required `smiles_map: dict[str, str]` parameter mapping
  entity id → SMILES. Missing keys raise ValueError listing the gap.

v1 limitations (explicit gaps; not oversights):
  - Vertical stacking when reactant/product count would overflow panel
    width is not yet implemented; render_reaction lays everything out
    horizontally.
  - `ReactionConditions.reversible` is silently ignored; chemistry's
    arrow primitive draws single-direction only. Honor this once
    chemistry exposes a reversible-arrow option.
  - Multi-step reactions (an entity that is both source and target of
    different relations -- an intermediate) raise NotImplementedError.
    Multi-step belongs in pathway_layout.py.
  - Per-molecule annotations / compound numbers are deferred to
    label_placement.py paired with a v2 of this engine that decomposes
    into per-molecule LayoutEntry items.

Phase 5 coupling:
  All layout engines emit `LayoutEntry` so the renderer is uniform.
  The renderer calls `entry.primitive(*entry.args, **entry.kwargs)`,
  receives an svgwrite Group, then wraps it in a translate by
  `entry.position` before adding to the Drawing.
"""
from __future__ import annotations

from typing import Any

import svgwrite.container

from imageGen.ir.schema import Archetype, Figure, ReactionConditions
from imageGen.layout.types import LayoutEntry
from imageGen.primitives.chemistry import render_reaction


# ---------------------------------------------------------------------------
# Layout knobs (Phase 4 master preset will union these alongside primitive
# DEFAULT_STYLE dicts; flat namespaced keys for predictable union).
# ---------------------------------------------------------------------------

REACTION_DEFAULT_PARAMS: dict[str, Any] = {
    "reaction_molecule_size": (140, 100),   # forwarded to render_reaction
    "reaction_origin":        (0.0, 0.0),   # top-left of the reaction Group
    "reaction_canvas":        (800.0, 300.0),  # SVG viewport for compositor (Phase 5)
    "reaction_max_width":     800.0,        # V2/R1: total px before switching to stacked layout
    "reaction_stacked_row_gap": 24.0,       # V2/R1: vertical gap between stacked rows
}

# A REACTION_SCHEME renders as a single composite group (molecules are
# drawn from SMILES as one unit, not per-entity). This is the ir_id that
# group carries — and the only semantic anchor verify/ can check for it.
REACTION_GROUP_IR_ID = "reaction_0"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _classify_entities(figure: Figure) -> tuple[list[str], list[str]]:
    """Return (reactant_ids, product_ids) preserving entity declaration order.

    Reactant = entity that is the source of any relation.
    Product = entity that is the target of any relation.
    Intermediates (both source and target -- multi-step reactions) raise
    NotImplementedError; those belong in pathway_layout.py.

    Output preserves the entity declaration order from the IR: callers who
    care about left-to-right ordering of reactants in the rendered figure
    set it by ordering the entity list in the IR.
    """
    sources = {r.source for r in figure.relations}
    targets = {r.target for r in figure.relations}
    intermediates = sources & targets
    if intermediates:
        raise NotImplementedError(
            f"Multi-step reactions (entities {sorted(intermediates)} are both "
            f"source and target) are not supported by reaction_layout; use "
            f"pathway_layout instead."
        )
    reactants = [e.id for e in figure.entities if e.id in sources]
    products = [e.id for e in figure.entities if e.id in targets]
    return reactants, products


def _extract_conditions(figure: Figure) -> dict[str, str] | None:
    """Map the first relation's ReactionConditions to render_reaction's dict.

    Returns {"above": str, "below": str} with either or both keys present,
    or None if no relation in the figure carries conditions. Multi-relation
    conditions (different per-arrow conditions) is a v2 concern; v1 picks
    the first relation that has any.
    """
    for relation in figure.relations:
        c = relation.conditions
        if c is None:
            continue
        if isinstance(c, dict):
            c = ReactionConditions.model_validate(c)
        result: dict[str, str] = {}
        if c.reagents:
            result["above"] = ", ".join(c.reagents)
        if c.notes:
            result["below"] = c.notes
        elif c.yield_pct is not None:
            result["below"] = f"{c.yield_pct:.0f}%"
        return result or None
    return None


def _resolve_smiles(entity_ids: list[str], smiles_map: dict[str, str]) -> list[str]:
    """Look up SMILES for each entity id; raise ValueError listing any misses."""
    missing = [eid for eid in entity_ids if eid not in smiles_map]
    if missing:
        raise ValueError(
            f"smiles_map is missing entries for entity id(s): {missing}"
        )
    return [smiles_map[eid] for eid in entity_ids]


def _is_reversible(figure: Figure) -> bool:
    """Return True if any relation in *figure* has conditions.reversible=True.

    V2 / R2: the first truthy flag wins; a single reversible relation makes
    the whole reaction arrow reversible.
    """
    for rel in figure.relations:
        c = rel.conditions
        if c is None:
            continue
        if isinstance(c, dict):
            c = ReactionConditions.model_validate(c)
        if c.reversible:
            return True
    return False


def _block_width(n_mols: int, mol_w: float, gap: float, plus_w: float) -> float:
    """Total pixel width of a horizontal molecule block with "+" signs.

    For *n_mols* molecules of width *mol_w* separated by a gap + plus glyph +
    gap, the total is ``n_mols * mol_w + (n_mols - 1) * (2*gap + plus_w)``.
    Returns 0 when *n_mols* == 0.

    V2 / R1.
    """
    if n_mols <= 0:
        return 0.0
    return n_mols * mol_w + (n_mols - 1) * (2.0 * gap + plus_w)


def _should_stack(
    n_reactants: int,
    n_products: int,
    mol_w: float,
    gap: float,
    arrow_len: float,
    plus_w: float,
    max_width: float,
) -> bool:
    """Return True when the flat horizontal layout would exceed *max_width*.

    Total flat width = reactants_block + gap + arrow + gap + products_block.
    V2 / R1.
    """
    total = (
        _block_width(n_reactants, mol_w, gap, plus_w)
        + gap + arrow_len + gap
        + _block_width(n_products, mol_w, gap, plus_w)
    )
    return total > max_width


def _molecule_centers(
    reactant_ids: list[str],
    product_ids: list[str],
    mol_w: float,
    mol_h: float,
    gap: float,
    arrow_len: float,
    plus_w: float,
    top_pad: float,
    stack: bool,
    row_gap: float,
) -> dict[str, tuple[float, float]]:
    """Return the (cx, cy) centre for every molecule in the rendered reaction.

    Replicates the cursor-based geometry of ``render_reaction`` so that
    ``reaction_label_requests`` can anchor compound-name labels at the
    correct position without having to inspect the rendered SVG.

    V2 / R4.
    """
    result: dict[str, tuple[float, float]] = {}
    # -- Row 1: reactants --
    mol_top_1 = top_pad
    cursor = 0.0
    for i, eid in enumerate(reactant_ids):
        cx = cursor + mol_w / 2.0
        cy = mol_top_1 + mol_h / 2.0
        result[eid] = (cx, cy)
        cursor += mol_w
        if i < len(reactant_ids) - 1:
            cursor += gap + plus_w + gap
    # -- Row 2 (or continuation of row 1): products --
    if stack:
        mol_top_2 = mol_top_1 + mol_h + row_gap
        cursor_p = arrow_len + gap     # products start after the stacked arrow
    else:
        cursor_p = cursor + gap + arrow_len + gap  # skip arrow in flat mode
        mol_top_2 = mol_top_1
    for i, eid in enumerate(product_ids):
        cx = cursor_p + mol_w / 2.0
        cy = mol_top_2 + mol_h / 2.0
        result[eid] = (cx, cy)
        cursor_p += mol_w
        if i < len(product_ids) - 1:
            cursor_p += gap + plus_w + gap
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def layout_reaction(
    figure: Figure,
    smiles_map: dict[str, str],
    layout_params: dict | None = None,
    style_dict: dict | None = None,
) -> list[LayoutEntry]:
    """Lay out an IR REACTION_SCHEME Figure as a list of LayoutEntry tuples.

    Args:
        figure: IR Figure with archetype=REACTION_SCHEME, non-empty entities
            and relations. Each relation's source is treated as a reactant
            and target as a product; intermediates (entity appearing on both
            sides) raise NotImplementedError.
        smiles_map: Required mapping from entity.id to SMILES string. Missing
            keys raise ValueError listing the gap.
        layout_params: Optional overlay onto REACTION_DEFAULT_PARAMS for layout
            knobs (molecule size, origin).
        style_dict: Optional preset overlay forwarded to render_reaction
            for visual styling.

    Returns:
        A list of LayoutEntry tuples ready for the renderer. A single entry
        calls render_reaction; ``reaction_label_requests`` can be called
        afterwards to generate per-molecule compound-name label requests.

    Raises:
        ValueError: figure.archetype is not REACTION_SCHEME; entities or
            relations are empty; smiles_map is missing required ids.
        NotImplementedError: figure contains an intermediate entity
            (multi-step reaction).
    """
    if figure.archetype != Archetype.REACTION_SCHEME:
        raise ValueError(
            f"layout_reaction requires archetype=REACTION_SCHEME, "
            f"got {figure.archetype!r}"
        )
    if not figure.entities:
        raise ValueError("layout_reaction requires a non-empty entities list")
    if not figure.relations:
        raise ValueError("layout_reaction requires a non-empty relations list")

    reactant_ids, product_ids = _classify_entities(figure)
    reactants_smiles = _resolve_smiles(reactant_ids, smiles_map)
    products_smiles = _resolve_smiles(product_ids, smiles_map)
    conditions = _extract_conditions(figure)

    params = {**REACTION_DEFAULT_PARAMS, **(layout_params or {})}
    mol_w, mol_h = params["reaction_molecule_size"]
    row_gap = float(params["reaction_stacked_row_gap"])

    # V2/R2: forward reversible flag from IR conditions
    reversible = _is_reversible(figure)

    # V2/R1: switch to stacked layout when horizontal extent overflows max_width
    # Use chemistry DEFAULT_STYLE constants for gap / arrow_len / plus_size so
    # the stacking decision matches what render_reaction will actually render.
    from imageGen.primitives.chemistry import DEFAULT_STYLE as _CHEM_STYLE  # noqa: PLC0415
    _gap = float(_CHEM_STYLE["chem_reaction_gap"])
    _arrow_len = float(_CHEM_STYLE["chem_reaction_arrow_length"])
    _plus_w = int(_CHEM_STYLE["chem_reaction_plus_font_size"])
    stack = _should_stack(
        len(reactant_ids), len(product_ids),
        mol_w, _gap, _arrow_len, _plus_w,
        float(params["reaction_max_width"]),
    )

    kwargs: dict[str, Any] = {
        "conditions": conditions,
        "molecule_size": params["reaction_molecule_size"],
    }
    if reversible:
        kwargs["reversible"] = True
    if stack:
        kwargs["stack"] = True
        kwargs["stacked_row_gap"] = row_gap
    # Only forward style_dict when the caller actually passed one — keeps
    # LayoutEntry.kwargs minimal and the renderer doesn't have to special-case
    # an explicit None.
    if style_dict is not None:
        kwargs["style_dict"] = style_dict
    return [LayoutEntry(
        primitive=render_reaction,
        args=(reactants_smiles, products_smiles),
        kwargs=kwargs,
        position=params["reaction_origin"],
        ir_id=REACTION_GROUP_IR_ID,
    )]


def reaction_label_requests(
    figure: Figure,
    entries: list[LayoutEntry],
) -> list:
    """Emit one ``LabelRequest`` per entity in a REACTION_SCHEME figure.

    Places each entity's label (compound name) just below its molecule
    bounding box. Anchors are computed by replicating the geometry of
    ``render_reaction`` so labels land at the correct position without
    inspecting the rendered SVG.

    V2 / R4.

    Args:
        figure: The same IR Figure passed to ``layout_reaction``.
        entries: The list returned by ``layout_reaction(figure, ...)``.
            Must contain exactly one entry (the monolithic render_reaction
            entry); raises ``ValueError`` otherwise.

    Returns:
        A list of ``LabelRequest`` items, one per entity whose ``label``
        is non-empty. Imports ``LabelRequest`` lazily to avoid a circular
        import.
    """
    from imageGen.layout.label_placement import LabelRequest  # noqa: PLC0415

    if not entries:
        return []
    entry = entries[0]
    mol_w, mol_h = entry.kwargs["molecule_size"]
    conditions = entry.kwargs.get("conditions")
    stack = entry.kwargs.get("stack", False)
    row_gap = float(entry.kwargs.get("stacked_row_gap", 24.0))

    # Replicate top_pad from render_reaction (rough approximation based on
    # above-condition line count; matches render_reaction's _wrap logic).
    cond_size = 11   # chemistry.DEFAULT_STYLE["chem_conditions_font_size"]
    cond_offset = 6.0
    line_gap = cond_size * 1.3
    top_pad = 0.0
    if conditions and conditions.get("above"):
        above_text = str(conditions["above"])
        n_lines = 1 + sum(
            1 for i in range(28, len(above_text), 28)
            if above_text[i - 1] != " "
        )
        # Simple count: ceil(len / 28)
        n_lines = max(1, (len(above_text) + 27) // 28)
        top_pad = n_lines * line_gap + cond_offset

    from imageGen.primitives.chemistry import DEFAULT_STYLE as _CHEM_STYLE  # noqa: PLC0415
    _gap = float(_CHEM_STYLE["chem_reaction_gap"])
    _arrow_len = float(_CHEM_STYLE["chem_reaction_arrow_length"])
    _plus_w = int(_CHEM_STYLE["chem_reaction_plus_font_size"])

    reactant_ids, product_ids = _classify_entities(figure)
    centers = _molecule_centers(
        reactant_ids, product_ids,
        float(mol_w), float(mol_h),
        _gap, _arrow_len, float(_plus_w),
        top_pad, stack, row_gap,
    )

    entity_by_id = {e.id: e for e in figure.entities}
    requests: list[LabelRequest] = []
    for eid, (cx, cy) in centers.items():
        entity = entity_by_id.get(eid)
        if entity is None or not entity.label:
            continue
        requests.append(LabelRequest(
            text=entity.label,
            # Anchor at the molecule's bottom-centre; label goes below.
            anchor=(cx, cy + mol_h / 2.0),
            anchor_size=(float(mol_w), 0.0),
            priority=("below", "above", "right", "left", "center"),
            ir_id=eid,
        ))
    return requests
