"""Shared geometry and primitive-dispatch tables for the layout package.

These tables are keyed by `EntityType` and consumed by multiple layout
engines, so they live here rather than inside any one engine. Keep
`ENTITY_BBOX` in sync if a primitive's default size changes; Phase 4's
master preset will eventually centralise this so the bbox can come from
style instead of a hard-coded table.
"""
from __future__ import annotations

from typing import Callable

import svgwrite.container

from imageGen.ir.schema import EntityType
from imageGen.primitives import proteins

# Per-EntityType bounding boxes (w, h), tracking each primitive's default
# size in `primitives/proteins.py`. Used to inset arrow endpoints to the
# entity's perimeter so shafts/heads never overlap entity labels, and
# (in label_placement) to compute the bbox of an entity LayoutEntry for
# collision-aware label anchoring.
ENTITY_BBOX: dict[EntityType, tuple[float, float]] = {
    EntityType.PROTEIN:    (60.0, 30.0),
    EntityType.LIGAND:     (60.0, 30.0),
    EntityType.RECEPTOR:   (28.0, 60.0),
    EntityType.KINASE:     (70.0, 32.0),
    EntityType.GENE:       (60.0, 30.0),
    EntityType.METABOLITE: (60.0, 30.0),
    EntityType.CELL:       (60.0, 30.0),
    EntityType.ORGANELLE:  (60.0, 30.0),
    EntityType.EQUIPMENT:  (60.0, 30.0),
    EntityType.SAMPLE:     (60.0, 30.0),
    EntityType.GENERIC:    (60.0, 30.0),
}

# EntityType → primitive callable. Pathway layout uses this to render
# entities; label_placement uses the reverse lookup (primitive → bbox)
# when anchoring labels to entity LayoutEntries.
ENTITY_TO_PRIMITIVE: dict[EntityType, Callable[..., svgwrite.container.Group]] = {
    EntityType.PROTEIN:    proteins.generic_protein,
    EntityType.LIGAND:     proteins.generic_protein,
    EntityType.RECEPTOR:   proteins.receptor,
    EntityType.KINASE:     proteins.kinase,
    EntityType.GENE:       proteins.generic_protein,
    EntityType.METABOLITE: proteins.generic_protein,
    EntityType.CELL:       proteins.generic_protein,
    EntityType.ORGANELLE:  proteins.generic_protein,
    EntityType.EQUIPMENT:  proteins.generic_protein,
    EntityType.SAMPLE:     proteins.generic_protein,
    EntityType.GENERIC:    proteins.generic_protein,
}
