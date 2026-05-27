"""LT7 + LT8 — RNA entity dispatch and DSB style wiring through layout_pathway."""
import re

from imageGen.layout.pathway_layout import layout_pathway
from imageGen.primitives import nucleic_acids

from tests._helpers import load_fixture


def _entry_by_irid(entries, ir_id):
    return next(e for e in entries if e.ir_id == ir_id)


def _polyline_x_coords(svg: str) -> list[float]:
    xs: list[float] = []
    for pts in re.findall(r'points="([^"]+)"', svg):
        for pair in pts.split():
            xs.append(float(pair.split(",")[0]))
    return xs


def test_rna_entity_dispatches_to_rna_helix():
    fig = load_fixture("crispr_cas9.json")
    entries = layout_pathway(fig)
    sgrna = _entry_by_irid(entries, "sgrna")
    assert sgrna.primitive is nucleic_acids.rna_helix
    # And it renders orange, distinct from the DNA entities.
    svg = sgrna.primitive(*sgrna.args, **sgrna.kwargs).tostring().upper()
    assert "E65100" in svg and "1565C0" not in svg


def test_dna_entity_still_dispatches_to_gene_helix():
    fig = load_fixture("crispr_cas9.json")
    entries = layout_pathway(fig)
    dna = _entry_by_irid(entries, "dna")
    assert dna.primitive is nucleic_acids.gene_helix


def test_dsb_entity_renders_broken_via_style():
    fig = load_fixture("crispr_cas9.json")
    entries = layout_pathway(fig)
    dsb = _entry_by_irid(entries, "dsb")
    assert dsb.primitive is nucleic_acids.gene_helix
    # The dna_break style key must have been forwarded into the primitive.
    assert dsb.kwargs.get("style_dict", {}).get("dna_break") is True
    # Rendered helix has a coordinate gap; an intact DNA entity does not.
    dsb_svg = dsb.primitive(*dsb.args, **dsb.kwargs).tostring()
    dna = _entry_by_irid(entries, "dna")
    dna_svg = dna.primitive(*dna.args, **dna.kwargs).tostring()

    cx = dsb.args[1][0]
    dsb_xs = _polyline_x_coords(dsb_svg)
    # No strand points in a tight window around the break centre.
    assert dsb_xs and not [x for x in dsb_xs if abs(x - cx) < 3.0]
    # The intact Target DNA helix, by contrast, has points spanning its centre.
    dna_cx = dna.args[1][0]
    dna_xs = _polyline_x_coords(dna_svg)
    assert [x for x in dna_xs if abs(x - dna_cx) < 6.0]
