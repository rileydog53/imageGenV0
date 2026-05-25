"""Tests for layout/_geom.py — ENTITY_BBOX synchronization.

C5 guard: asserts that ENTITY_BBOX values match each dispatched primitive's
default `size` parameter so any future drift is caught automatically.
"""
import inspect

from imageGen.layout._geom import ENTITY_BBOX, ENTITY_TO_PRIMITIVE


def test_entity_bbox_matches_primitive_defaults():
    """Every entry in ENTITY_BBOX must equal the dispatched primitive's default size.

    When a primitive's default size changes, update _geom.py to match.
    """
    for entity_type, primitive in ENTITY_TO_PRIMITIVE.items():
        sig = inspect.signature(primitive)
        if "size" not in sig.parameters:
            continue
        default_size = sig.parameters["size"].default
        if default_size is inspect.Parameter.empty:
            continue
        expected = tuple(float(x) for x in default_size)
        actual = ENTITY_BBOX[entity_type]
        assert actual == expected, (
            f"ENTITY_BBOX[{entity_type!r}] = {actual} does not match "
            f"{primitive.__name__} default size = {default_size}. "
            f"Update ENTITY_BBOX in layout/_geom.py."
        )
