"""Tests for render/cli.py — Phase 5 Step 6.

Covers the argparse CLI wrapper around `render_figure`, exercised both
through direct `main()` calls and via one end-to-end `python -m imageGen`
subprocess invocation.
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest
from PIL import Image

from imageGen.render.cli import main
from tests._helpers import FIXTURES_DIR

MAPK = str(FIXTURES_DIR / "mapk_cascade.json")
OXIDATION = str(FIXTURES_DIR / "oxidation_reaction.json")

OXIDATION_SMILES = {"alcohol": "CCO", "aldehyde": "CC=O"}


def test_main_writes_svg(tmp_path):
    out = tmp_path / "fig.svg"
    rc = main([MAPK, "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 0


def test_main_writes_png_readable_by_pillow(tmp_path):
    out = tmp_path / "fig.png"
    rc = main([MAPK, "-o", str(out)])
    assert rc == 0
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.width > 0 and img.height > 0


def test_main_writes_pdf(tmp_path):
    out = tmp_path / "fig.pdf"
    rc = main([MAPK, "-o", str(out)])
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF-")


def test_main_accepts_style_nature(tmp_path):
    out = tmp_path / "fig.svg"
    rc = main([MAPK, "-o", str(out), "--style", "nature"])
    assert rc == 0
    assert out.exists()


def test_main_loads_smiles_map_for_reaction_scheme(tmp_path):
    smiles_path = tmp_path / "smiles.json"
    smiles_path.write_text(json.dumps(OXIDATION_SMILES))
    out = tmp_path / "fig.svg"
    rc = main([OXIDATION, "-o", str(out), "--smiles-map", str(smiles_path)])
    assert rc == 0
    assert out.exists()


def test_python_m_invocation_writes_file(tmp_path):
    out = tmp_path / "fig.svg"
    result = subprocess.run(
        [sys.executable, "-m", "imageGen", MAPK, "-o", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert out.exists()
    assert str(out) in result.stdout


def test_main_rejects_unknown_format(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main([MAPK, "-o", str(tmp_path / "fig.png"), "--format", "foo"])
    assert excinfo.value.code == 2
