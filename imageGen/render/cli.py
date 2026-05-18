"""Command-line entry point for imageGen.

Wraps `render_figure` so an IR JSON file can be rendered from the shell:

    python -m imageGen IR_PATH --output OUT [--style ...] [--format ...]
                                 [--dpi N] [--smiles-map FILE.json]
                                 [--no-labels]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import get_args

from imageGen.ir.schema import Figure
from imageGen.render.compositor import Format, render_figure
from imageGen.styles.loader import list_presets


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m imageGen",
        description="Render an imageGen IR JSON file to SVG, PNG, or PDF.",
    )
    parser.add_argument("ir_path", metavar="IR_PATH", help="Path to IR JSON file.")
    parser.add_argument(
        "-o", "--output", required=True, help="Output file path."
    )
    parser.add_argument(
        "--style",
        choices=list_presets(),
        default=None,
        help="Journal style preset (overrides ir.style_preset).",
    )
    parser.add_argument(
        "--format",
        choices=get_args(Format),
        default=None,
        help="Output format (inferred from --output suffix when omitted).",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="Output resolution (default 300)."
    )
    parser.add_argument(
        "--smiles-map",
        default=None,
        help="Path to JSON file mapping entity ids to SMILES strings "
        "(required for REACTION_SCHEME figures).",
    )
    parser.add_argument(
        "--no-labels",
        dest="labels",
        action="store_false",
        help="Suppress automatic label placement.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    ir = Figure.model_validate_json(Path(args.ir_path).read_text())

    smiles_map = None
    if args.smiles_map is not None:
        smiles_map = json.loads(Path(args.smiles_map).read_text())

    out = render_figure(
        ir,
        args.output,
        style_name=args.style,
        format=args.format,
        smiles_map=smiles_map,
        labels=args.labels,
        dpi=args.dpi,
    )
    print(out)
    return 0
