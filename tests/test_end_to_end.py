"""End-to-end pipeline tests — Phase 8.

The Phase 6 suite checks each stage in isolation; this module is the
acceptance test for the *whole* pipeline: a fixture IR is rendered with the
public ``render_figure`` entry point and then audited by all three Phase 6
verifiers against the rendered SVG. A pass means classify-free IR → layout →
render → verify holds together for every wired archetype.

Label-overflow behavior is pinned here as *documented* behavior rather than
hidden: the three dense fixtures that exhaust the greedy label engine now
render through the full pipeline with labels on — the v2 relax-and-retry
ladder lands the last-resort labels with ``data-overlap="true"`` and
``legibility_check`` tolerates those deliberate collisions. The same fixtures
still raise ``LabelPlacementError`` when the caller opts into
``strict_labels=True``, and render cleanly with labels off.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from imageGen.ir.schema import Archetype
from imageGen.layout.label_placement import LabelPlacementError
from imageGen.render.compositor import render_figure
from imageGen.verify.convention_check import convention_check
from imageGen.verify.legibility_check import legibility_check
from imageGen.verify.semantic_check import semantic_check
from tests._helpers import load_fixture

# One clean-rendering fixture per wired archetype, mapped to its smiles_map
# (REACTION_SCHEME requires one per D4; everything else passes None).
# MECHANISM_CARTOON has no labels-on clean fixture — it is covered separately
# by test_mechanism_cartoon_pipeline_labels_off.
CLEAN_CASES: dict[str, dict[str, str] | None] = {
    "mapk_cascade.json": None,  # PATHWAY
    "simple_reaction.json": {  # REACTION_SCHEME
        "acid": "CC(=O)O",
        "alcohol": "CCO",
        "ester": "CCOC(C)=O",
    },
    "three_panel_workflow.json": None,  # WORKFLOW
    "cellular_schematic.json": None,  # CELLULAR_SCHEMATIC
}

# Fixtures that overflow the greedy label engine with labels on (BACKLOG
# L2/L14). They render fine with labels=False.
LABEL_OVERFLOW_FIXTURES = [
    "graphical_abstract_mrna_vaccine.json",
    "mechanism_cartoon.json",
    "western_blot_schematic.json",
]


def _run_pipeline(
    fixture_name: str,
    out_dir: Path,
    *,
    smiles_map: dict[str, str] | None = None,
    labels: bool = True,
) -> None:
    """Render a fixture and audit it with all three Phase 6 verifiers.

    Renders to PNG (which also writes the sibling SVG the verifiers parse),
    asserts the PNG is non-empty, then runs semantic, legibility, and
    convention checks. Any verifier failure propagates as the test failure.
    """
    ir = load_fixture(fixture_name)
    png = render_figure(
        ir,
        out_dir / f"{Path(fixture_name).stem}.png",
        smiles_map=smiles_map,
        labels=labels,
    )
    assert png.exists() and png.stat().st_size > 0, f"empty render for {fixture_name}"

    svg = png.with_suffix(".svg")
    assert svg.exists(), f"sibling SVG missing for {fixture_name}"

    semantic_check(ir, svg)
    legibility_check(svg)
    convention_check(ir, svg)


@pytest.mark.parametrize("fixture_name", sorted(CLEAN_CASES))
def test_end_to_end_pipeline(fixture_name: str, tmp_path: Path) -> None:
    """Each wired archetype renders and passes all three verifiers."""
    _run_pipeline(fixture_name, tmp_path, smiles_map=CLEAN_CASES[fixture_name])


def test_mechanism_cartoon_pipeline_labels_off(tmp_path: Path) -> None:
    """MECHANISM_CARTOON completes the full pipeline with labels suppressed."""
    _run_pipeline("mechanism_cartoon.json", tmp_path, labels=False)


def test_every_wired_archetype_is_covered() -> None:
    """The clean cases plus mechanism_cartoon exercise all 5 wired archetypes."""
    covered = {load_fixture(name).archetype for name in CLEAN_CASES}
    covered.add(load_fixture("mechanism_cartoon.json").archetype)
    assert covered == {
        Archetype.PATHWAY,
        Archetype.REACTION_SCHEME,
        Archetype.WORKFLOW,
        Archetype.CELLULAR_SCHEMATIC,
        Archetype.MECHANISM_CARTOON,
    }


@pytest.mark.parametrize("fixture_name", LABEL_OVERFLOW_FIXTURES)
def test_dense_fixture_renders_with_labels_on(
    fixture_name: str, tmp_path: Path
) -> None:
    """Dense fixtures now complete the full pipeline with labels on.

    Previously all three raised ``LabelPlacementError``; the v2 relax-and-retry
    ladder places every label (shrinking, nudging, or — last resort — landing
    with ``data-overlap="true"`` which ``legibility_check`` tolerates). Some
    fixtures emit a UserWarning about a last-resort overlap; that's expected
    and not a failure.
    """
    _run_pipeline(fixture_name, tmp_path, labels=True)


@pytest.mark.parametrize("fixture_name", LABEL_OVERFLOW_FIXTURES)
def test_strict_labels_matches_lenient_overlap(
    fixture_name: str, tmp_path: Path
) -> None:
    """Contract: a fixture lands a last-resort overlap (lenient) iff it raises
    in strict mode. Fixtures the ladder fully resolves succeed in both modes.
    """
    ir = load_fixture(fixture_name)
    out = tmp_path / f"{Path(fixture_name).stem}.png"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        render_figure(ir, out, labels=True)
    overlapped = any("overlap" in str(w.message) for w in caught)

    if overlapped:
        with pytest.raises(LabelPlacementError):
            render_figure(ir, out, labels=True, strict_labels=True)
    else:
        # Ladder fully resolved every label — strict mode succeeds too.
        render_figure(ir, out, labels=True, strict_labels=True)


@pytest.mark.parametrize("fixture_name", LABEL_OVERFLOW_FIXTURES)
def test_dense_fixture_renders_with_labels_off(
    fixture_name: str, tmp_path: Path
) -> None:
    """The same dense fixtures render cleanly once labels are suppressed."""
    _run_pipeline(fixture_name, tmp_path, labels=False)
