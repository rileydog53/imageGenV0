"""Regenerate the worked-example figures in this directory.

One figure per archetype, ordered by complexity. These double as the v1
"one worked example per archetype" deliverable and as a human-facing demo
of what imageGen produces. Run from anywhere::

    ~/Desktop/.venv/bin/python references/examples/generate_examples.py

Each example renders a checked-in fixture from ``tests/fixtures/`` through
the public ``render_figure`` pipeline, so the output stays in lockstep with
the library.
"""
from __future__ import annotations

import json
from pathlib import Path

from imageGen.ir.schema import Figure
from imageGen.render.compositor import render_figure

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
OUT_DIR = Path(__file__).resolve().parent

# (output stem, fixture file, smiles_map, labels) — ordered by complexity.
EXAMPLES: list[tuple[str, str, dict[str, str] | None, bool]] = [
    (
        "01_reaction_scheme",
        "simple_reaction.json",
        {"acid": "CC(=O)O", "alcohol": "CCO", "ester": "CCOC(C)=O"},
        True,
    ),
    ("02_pathway", "simple_activation.json", None, True),
    ("03_mechanism_cartoon", "mechanism_cartoon.json", None, False),
    ("04_cellular_schematic", "cellular_schematic.json", None, True),
    ("05_workflow", "three_panel_workflow.json", None, True),
]


def main() -> None:
    for stem, fixture, smiles_map, labels in EXAMPLES:
        ir = Figure.model_validate(json.loads((FIXTURES / fixture).read_text()))
        out = render_figure(
            ir,
            OUT_DIR / f"{stem}.png",
            smiles_map=smiles_map,
            labels=labels,
        )
        print(f"  {out.relative_to(REPO_ROOT)}  ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
