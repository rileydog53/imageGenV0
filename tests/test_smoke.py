"""Phase 0 smoke tests: imports and environment checks only."""
import subprocess
import sys


def test_python_version():
    assert sys.version_info >= (3, 12), f"Expected Python 3.12+, got {sys.version}"


def test_venv():
    assert "Desktop/.venv" in sys.executable, (
        f"Not running in Desktop venv. sys.executable={sys.executable}"
    )


# --- third-party package imports ---

def test_import_rdkit():
    import rdkit  # noqa: F401
    from rdkit import Chem
    mol = Chem.MolFromSmiles("CCO")
    assert mol is not None, "RDKit parsed ethanol to None — build may be broken"


def test_import_cairo():
    import cairo  # noqa: F401


def test_import_svgwrite():
    import svgwrite  # noqa: F401


def test_import_svgutils():
    import svgutils  # noqa: F401


def test_import_networkx():
    import networkx  # noqa: F401


def test_import_numpy():
    import numpy  # noqa: F401


def test_import_scipy():
    import scipy  # noqa: F401


def test_import_pillow():
    import PIL  # noqa: F401


def test_import_pydantic():
    import pydantic  # noqa: F401


def test_import_cairosvg():
    import cairosvg  # noqa: F401


def test_import_matplotlib():
    import matplotlib  # noqa: F401


def test_cairosvg_roundtrip():
    """cairosvg can convert a minimal SVG to PNG bytes without crashing."""
    import cairosvg
    minimal_svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    png = cairosvg.svg2png(bytestring=minimal_svg)
    assert len(png) > 0, "cairosvg produced empty output"


# --- project module imports ---

def test_import_ir():
    import ir.schema  # noqa: F401


def test_import_archetypes():
    import archetypes.pathway  # noqa: F401
    import archetypes.reaction_scheme  # noqa: F401
    import archetypes.workflow  # noqa: F401
    import archetypes.cellular_schematic  # noqa: F401
    import archetypes.mechanism_cartoon  # noqa: F401


def test_import_primitives():
    import primitives.arrows  # noqa: F401
    import primitives.proteins  # noqa: F401
    import primitives.membranes  # noqa: F401
    import primitives.nucleic_acids  # noqa: F401
    import primitives.cells  # noqa: F401
    import primitives.chemistry  # noqa: F401
    import primitives.lab_equipment  # noqa: F401


def test_import_layout():
    import layout.pathway_layout  # noqa: F401
    import layout.reaction_layout  # noqa: F401
    import layout.panel_layout  # noqa: F401
    import layout.label_placement  # noqa: F401


def test_import_styles():
    import styles.loader  # noqa: F401


def test_import_render():
    import render.compositor  # noqa: F401
    import render.export  # noqa: F401
    import render.cli  # noqa: F401


def test_import_verify():
    import verify.semantic_check  # noqa: F401
    import verify.legibility_check  # noqa: F401
    import verify.convention_check  # noqa: F401


# --- directory structure ---

def test_directory_structure():
    from pathlib import Path
    root = Path(__file__).parent.parent
    required = [
        "ir/schema.py",
        "archetypes/pathway.py", "archetypes/reaction_scheme.py",
        "archetypes/workflow.py", "archetypes/cellular_schematic.py",
        "archetypes/mechanism_cartoon.py",
        "primitives/arrows.py", "primitives/proteins.py",
        "primitives/membranes.py", "primitives/nucleic_acids.py",
        "primitives/cells.py", "primitives/chemistry.py",
        "primitives/lab_equipment.py",
        "layout/pathway_layout.py", "layout/reaction_layout.py",
        "layout/panel_layout.py", "layout/label_placement.py",
        "styles/loader.py",
        "render/compositor.py", "render/export.py", "render/cli.py",
        "verify/semantic_check.py", "verify/legibility_check.py",
        "verify/convention_check.py",
        "references/journal_conventions.md",
        "tests/fixtures", "tests/figures",
        "README.md",
    ]
    missing = [p for p in required if not (root / p).exists()]
    assert not missing, f"Missing from project tree: {missing}"
