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

from imageGenV0.ir.schema import Archetype, Figure, ReactionConditions
from imageGenV0.layout.types import LayoutEntry
from imageGenV0.primitives.chemistry import render_reaction


# ---------------------------------------------------------------------------
# Layout knobs (Phase 4 master preset will union these alongside primitive
# DEFAULT_STYLE dicts; flat namespaced keys for predictable union).
# ---------------------------------------------------------------------------

DEFAULT_LAYOUT_PARAMS: dict[str, Any] = {
    "reaction_molecule_size": (140, 100),   # forwarded to render_reaction
    "reaction_origin":        (0.0, 0.0),   # top-left of the reaction Group
    "reaction_canvas":        (800.0, 300.0),  # SVG viewport for compositor (Phase 5)
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
        layout_params: Optional overlay onto DEFAULT_LAYOUT_PARAMS for layout
            knobs (molecule size, origin).
        style_dict: Optional preset overlay forwarded to render_reaction
            for visual styling.

    Returns:
        A list of LayoutEntry tuples ready for the renderer. v1 always
        returns a single entry calling render_reaction; v2 will decompose
        into per-molecule entries when label_placement.py is ready.

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

    params = {**DEFAULT_LAYOUT_PARAMS, **(layout_params or {})}
    kwargs: dict[str, Any] = {
        "conditions": conditions,
        "molecule_size": params["reaction_molecule_size"],
    }
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
