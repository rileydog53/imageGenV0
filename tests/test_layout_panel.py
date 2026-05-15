"""Phase 3 Step 3 tests for layout/panel_layout.py."""
from __future__ import annotations

import pytest
import svgwrite
import svgwrite.container

from imageGenV0.ir.schema import (
    Archetype, Entity, EntityType, Figure, Panel, Relation, RelationType,
)
from imageGenV0.layout.panel_layout import (
    ARCHETYPE_TO_LAYOUT,
    DEFAULT_LAYOUT_PARAMS,
    _cell_size,
    _grid_extent,
    _panel_chrome,
    _panel_rect,
    layout_panel,
)
from imageGenV0.layout.pathway_layout import layout_pathway
from imageGenV0.layout.reaction_layout import layout_reaction
from imageGenV0.layout.types import LayoutEntry
from tests._helpers import load_fixture, render_entries_to_png


def _chrome_entries(entries: list[LayoutEntry]) -> list[LayoutEntry]:
    return [e for e in entries if e.primitive is _panel_chrome]


def _make_workflow_figure(n_panels: int = 2) -> Figure:
    """Build a small panels-only Figure with n_panels in a single row."""
    panels = []
    for i in range(n_panels):
        panels.append(Panel(
            id=f"p{i}",
            title=f"Step {i + 1}",
            grid=(0, i, 1, 1),
            content=Figure(
                archetype=Archetype.WORKFLOW,
                entities=[
                    Entity(id=f"a{i}", type=EntityType.SAMPLE, label=f"A{i}"),
                    Entity(id=f"b{i}", type=EntityType.SAMPLE, label=f"B{i}"),
                ],
                relations=[
                    Relation(source=f"a{i}", target=f"b{i}",
                             type=RelationType.GENERIC),
                ],
            ),
        ))
    return Figure(archetype=Archetype.WORKFLOW, panels=panels)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_empty_panels_raises():
    fig = Figure(archetype=Archetype.WORKFLOW)
    with pytest.raises(ValueError, match="panels"):
        layout_panel(fig)


def test_nested_panels_raise_not_implemented():
    inner = Figure(archetype=Archetype.WORKFLOW, panels=[
        Panel(id="inner", grid=(0, 0, 1, 1), content=Figure(
            archetype=Archetype.PATHWAY,
            entities=[Entity(id="x", type=EntityType.GENERIC, label="X")],
        )),
    ])
    outer = Figure(archetype=Archetype.WORKFLOW, panels=[
        Panel(id="outer", grid=(0, 0, 1, 1), content=inner),
    ])
    with pytest.raises(NotImplementedError, match="Nested"):
        layout_panel(outer)


# ---------------------------------------------------------------------------
# Grid math
# ---------------------------------------------------------------------------

def test_grid_extent_three_in_a_row():
    fig = load_fixture("three_panel_workflow.json")
    rows, cols = _grid_extent(fig)
    assert (rows, cols) == (1, 3)


def test_cell_size_partitions_canvas_minus_margins_and_gutters():
    cw, ch = 1200.0, 600.0
    margin, gutter = 20.0, 10.0
    rows, cols = 1, 3
    w, h = _cell_size((cw, ch), margin, gutter, rows, cols)
    assert w == pytest.approx((cw - 2 * margin - gutter * 2) / 3)
    assert h == pytest.approx(ch - 2 * margin)


def test_panel_rects_do_not_overlap():
    fig = load_fixture("three_panel_workflow.json")
    entries = layout_panel(fig)
    chromes = _chrome_entries(entries)
    rects = [(e.args[1], e.args[2], e.args[3], e.args[4]) for e in chromes]
    for i, (x1, y1, w1, h1) in enumerate(rects):
        for x2, y2, w2, h2 in rects[i + 1:]:
            overlaps_x = x1 < x2 + w2 and x2 < x1 + w1
            overlaps_y = y1 < y2 + h2 and y2 < y1 + h1
            assert not (overlaps_x and overlaps_y)


# ---------------------------------------------------------------------------
# Archetype dispatch
# ---------------------------------------------------------------------------

def test_dispatch_table_routes_workflow_to_pathway_engine():
    assert ARCHETYPE_TO_LAYOUT[Archetype.WORKFLOW] is layout_pathway
    assert ARCHETYPE_TO_LAYOUT[Archetype.PATHWAY] is layout_pathway
    assert ARCHETYPE_TO_LAYOUT[Archetype.REACTION_SCHEME] is layout_reaction


def test_unmapped_archetype_raises_not_implemented():
    """Force the failure path by stubbing out a panel's archetype to one
    that won't be in the table once we delete it for the call."""
    fig = _make_workflow_figure(n_panels=1)
    saved = ARCHETYPE_TO_LAYOUT.pop(Archetype.WORKFLOW)
    try:
        with pytest.raises(NotImplementedError, match="No layout engine"):
            layout_panel(fig)
    finally:
        ARCHETYPE_TO_LAYOUT[Archetype.WORKFLOW] = saved


def test_reaction_panel_requires_smiles_maps():
    """A reaction-scheme panel needs a per-panel SMILES map."""
    fig = Figure(archetype=Archetype.WORKFLOW, panels=[
        Panel(id="rxn", grid=(0, 0, 1, 1), content=Figure(
            archetype=Archetype.REACTION_SCHEME,
            entities=[
                Entity(id="r", type=EntityType.METABOLITE, label="R"),
                Entity(id="p", type=EntityType.METABOLITE, label="P"),
            ],
            relations=[Relation(source="r", target="p", type=RelationType.GENERIC)],
        )),
    ])
    with pytest.raises(ValueError, match="smiles_maps"):
        layout_panel(fig)


# ---------------------------------------------------------------------------
# Position offsets — first real consumer of LayoutEntry.position
# ---------------------------------------------------------------------------

def test_sub_entries_are_offset_into_their_panel_cell():
    fig = _make_workflow_figure(n_panels=2)
    entries = layout_panel(fig)
    chromes = _chrome_entries(entries)
    chrome_by_panel_x = {e.args[1] for e in chromes}

    # Every non-chrome entry's position must land in some panel's x-range.
    chrome_rects = [(e.args[1], e.args[2], e.args[3], e.args[4]) for e in chromes]
    for entry in entries:
        if entry.primitive is _panel_chrome:
            continue
        px, _ = entry.position
        # at least one chrome rect contains px (loose check; the x-offset
        # from _shift_entry is the panel's left edge).
        assert any(rx <= px < rx + rw for rx, _, rw, _ in chrome_rects)


def test_chrome_disabled_emits_no_chrome_entries():
    fig = _make_workflow_figure(n_panels=2)
    entries = layout_panel(fig, layout_params={"panel_show_chrome": False})
    assert _chrome_entries(entries) == []


def test_chrome_enabled_by_default_emits_one_per_panel():
    fig = _make_workflow_figure(n_panels=3)
    entries = layout_panel(fig)
    assert len(_chrome_entries(entries)) == 3


# ---------------------------------------------------------------------------
# Forwarding to sub-engines
# ---------------------------------------------------------------------------

def test_pathway_subengine_canvas_matches_panel_cell():
    """The sub-engine should be told its canvas is the panel cell size, so
    its emitted positions live inside the cell — chrome rect dimensions
    bound the entries' positions accordingly."""
    fig = _make_workflow_figure(n_panels=2)
    entries = layout_panel(fig)
    chrome = _chrome_entries(entries)[0]
    _, cx, cy, cw, ch = chrome.args
    title_h = DEFAULT_LAYOUT_PARAMS["panel_title_height"]
    # entries shifted into this chrome must satisfy
    #   cx <= position_x < cx + cw
    #   cy + title_h <= position_y < cy + ch
    for e in entries:
        if e.primitive is _panel_chrome:
            continue
        x, y = e.position
        # Allow only entries whose x lies in any chrome's x-range; check
        # the *first* chrome's range here for the entries from panel 0.
        if not (cx <= x < cx + cw):
            continue
        assert cy + title_h - 1e-6 <= y < cy + ch + 1e-6


def test_style_dict_forwarded_to_subengines():
    fig = _make_workflow_figure(n_panels=1)
    style = {"protein_fill": "#FF0000"}
    entries = layout_panel(fig, style_dict=style)
    # at least one non-chrome entry should carry the style_dict through
    forwarded = [
        e for e in entries
        if e.primitive is not _panel_chrome
        and e.kwargs.get("style_dict") == style
    ]
    assert forwarded


# ---------------------------------------------------------------------------
# LayoutEntry shape
# ---------------------------------------------------------------------------

def test_entries_are_executable():
    fig = load_fixture("three_panel_workflow.json")
    entries = layout_panel(fig)
    for entry in entries:
        g = entry.primitive(*entry.args, **entry.kwargs)
        assert isinstance(g, svgwrite.container.Group)


def test_default_layout_params_keys_are_namespaced():
    for key in DEFAULT_LAYOUT_PARAMS:
        assert key.startswith("panel_"), f"non-namespaced key: {key}"


# ---------------------------------------------------------------------------
# Render-to-PNG (golden seed)
# ---------------------------------------------------------------------------

def test_render_three_panel_workflow_to_png():
    fig = load_fixture("three_panel_workflow.json")
    entries = layout_panel(fig)
    out = render_entries_to_png(entries, "layout_panel_three_workflow.png", canvas=(1200, 600))
    assert out.exists() and out.stat().st_size > 0
