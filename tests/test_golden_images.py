"""Golden-image regression tests — Phase 6 Step 4.

Each curated fixture IR is rendered to a PNG and compared, pixel-by-pixel,
against a checked-in golden image in ``tests/golden/``. A regression in any
layout engine, primitive, or the compositor shifts pixels and fails the
comparison — the silent-killer class of bug the other Phase 6 checks cannot
catch.

Goldens live apart from ``tests/figures/`` on purpose: the latter is rewritten
on every run by the ``render_*_to_png`` helpers and is not a stable baseline.

Regenerating goldens is opt-in and never silent. After an *intentional*
visual change::

    IMAGEGEN_REGEN_GOLDEN=1 ~/Desktop/.venv/bin/pytest tests/test_golden_images.py

In regen mode each golden test writes its image and is skipped instead of
compared. Eyeball the regenerated PNGs before committing them.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from imageGen.render.compositor import render_figure
from tests._helpers import compare_pngs, load_fixture

GOLDEN_DIR = Path(__file__).parent / "golden"

# Render at 1:1 (dpi 96) so committed goldens stay small — the default 300
# dpi would bloat the repo with large binaries.
GOLDEN_DPI = 96

# A pixel-diff fraction at or below this passes. compare_pngs already absorbs
# per-channel antialiasing noise; this absorbs the count of edge pixels that
# may shift across cairo/font-toolchain versions.
MAX_DIFF_FRACTION = 0.005

REGEN = os.environ.get("IMAGEGEN_REGEN_GOLDEN") == "1"

# Curated set: every fixture that renders cleanly through the default
# pipeline, mapped to its smiles_map. REACTION_SCHEME fixtures require one
# (D4); all other archetypes pass None.
#
# Three fixtures are deliberately excluded — graphical_abstract_mrna_vaccine,
# mechanism_cartoon, and western_blot_schematic each overflow the greedy label
# engine (LabelPlacementError; see BACKLOG L2/L14). Their archetypes are wired
# and render fine with labels off — but a golden should capture the default
# pipeline. Add them once the label engine gains a fallback.
GOLDEN_CASES: dict[str, dict[str, str] | None] = {
    "addition_reaction.json": {"alkene": "CC=C", "water": "O", "product": "CC(O)C"},
    "cellular_schematic.json": None,
    "drug_inhibition.json": None,
    "gpcr_signaling.json": None,
    "mapk_cascade.json": None,
    "multi_compartment_translocation.json": None,
    "oxidation_reaction.json": {"alcohol": "CCO", "aldehyde": "CC=O"},
    "simple_activation.json": None,
    "simple_reaction.json": {
        "acid": "CC(=O)O",
        "alcohol": "CCO",
        "ester": "CCOC(C)=O",
    },
    "substitution_reaction.json": {
        "alkyl_halide": "CCCBr",
        "nucleophile": "[K+].[OH-]",
        "alcohol": "CCCO",
    },
    "tf_transcription.json": None,
    "three_panel_workflow.json": None,
}


@pytest.mark.parametrize("fixture_name", sorted(GOLDEN_CASES))
def test_golden_image(fixture_name: str, tmp_path: Path) -> None:
    """Render a fixture and assert it matches its checked-in golden PNG."""
    stem = Path(fixture_name).stem
    ir = load_fixture(fixture_name)
    rendered = render_figure(
        ir,
        tmp_path / f"{stem}.png",
        smiles_map=GOLDEN_CASES[fixture_name],
        dpi=GOLDEN_DPI,
    )
    golden = GOLDEN_DIR / f"{stem}.png"

    if REGEN:
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_bytes(rendered.read_bytes())
        pytest.skip(f"regenerated golden: {golden.name}")

    assert golden.exists(), (
        f"missing golden {golden} — regenerate with IMAGEGEN_REGEN_GOLDEN=1"
    )
    diff = compare_pngs(golden, rendered)
    assert diff <= MAX_DIFF_FRACTION, (
        f"{fixture_name}: {diff:.4%} of pixels differ from the golden "
        f"(max {MAX_DIFF_FRACTION:.4%}) — a visual regression, or rerun with "
        f"IMAGEGEN_REGEN_GOLDEN=1 if the change is intentional"
    )


# ---------------------------------------------------------------------------
# compare_pngs helper
# ---------------------------------------------------------------------------


def test_compare_pngs_identical(tmp_path: Path) -> None:
    """Two renders of the same IR are byte-deterministic → zero diff."""
    ir = load_fixture("mapk_cascade.json")
    a = render_figure(ir, tmp_path / "a.png", dpi=GOLDEN_DPI)
    b = render_figure(ir, tmp_path / "b.png", dpi=GOLDEN_DPI)
    assert compare_pngs(a, b) == 0.0


def test_compare_pngs_detects_change(tmp_path: Path) -> None:
    """A different style preset shifts enough pixels to fail the threshold."""
    ir = load_fixture("mapk_cascade.json")
    a = render_figure(ir, tmp_path / "a.png", dpi=GOLDEN_DPI)
    b = render_figure(ir, tmp_path / "b.png", style_name="acs", dpi=GOLDEN_DPI)
    assert compare_pngs(a, b) > MAX_DIFF_FRACTION


def test_compare_pngs_size_mismatch_raises(tmp_path: Path) -> None:
    """Mismatched dimensions raise ValueError, not a silent bad comparison."""
    ir = load_fixture("mapk_cascade.json")
    a = render_figure(ir, tmp_path / "a.png", dpi=96)
    b = render_figure(ir, tmp_path / "b.png", dpi=192)
    with pytest.raises(ValueError, match="dimensions differ"):
        compare_pngs(a, b)
