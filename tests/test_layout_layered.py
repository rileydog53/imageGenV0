"""LT2 — layered (Sugiyama-style) DAG layout for compartment-free figures."""
import networkx as nx

from imageGen.layout._geom import ENTITY_TO_PRIMITIVE
from imageGen.layout._layered import order_within_ranks, rank_nodes, tighten_ranks
from imageGen.layout.pathway_layout import _feedback_arc_dag, layout_pathway
from imageGen.layout.types import LayoutEntry

from tests._helpers import load_fixture


def _entity_pos(entries: list[LayoutEntry]) -> dict[str, tuple[float, float]]:
    prims = set(ENTITY_TO_PRIMITIVE.values())
    return {
        e.ir_id: (e.args[1][0], e.args[1][1])
        for e in entries
        if e.primitive in prims and e.ir_id
    }


# --- rank_nodes -------------------------------------------------------------

def test_rank_is_longest_path_depth():
    # a→b→d and a→c→d ; d must rank after both b and c (longest path = 2).
    dag = nx.DiGraph([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
    ranks = rank_nodes(dag)
    assert ranks == {"a": 0, "b": 1, "c": 1, "d": 2}


def test_rank_convergence_uses_deepest_input():
    # Long arm a→b→c and short arm x→c: c sits past the longest arm.
    dag = nx.DiGraph([("a", "b"), ("b", "c"), ("x", "c")])
    ranks = rank_nodes(dag)
    assert ranks["c"] == 2  # max(rank b=1, rank x=0) + 1


def test_isolated_node_ranks_zero():
    dag = nx.DiGraph()
    dag.add_node("lonely")
    dag.add_edge("a", "b")
    ranks = rank_nodes(dag)
    assert ranks["lonely"] == 0


# --- tighten_ranks (LT10) ---------------------------------------------------

def test_tighten_pulls_cofactor_beside_its_consumer():
    # Backbone a→b→c→d (ranks 0..3); cofactor v feeds d only. ASAP pins v at 0
    # (no predecessors); tightening pulls it to rank 2 (one left of d).
    dag = nx.DiGraph([("a", "b"), ("b", "c"), ("c", "d"), ("v", "d")])
    asap = rank_nodes(dag)
    assert asap["v"] == 0
    tight = tighten_ranks(dag, asap)
    assert tight["v"] == 2          # min(rank d = 3) - 1
    # Backbone (zero-slack critical path) is unchanged.
    assert (tight["a"], tight["b"], tight["c"], tight["d"]) == (0, 1, 2, 3)


def test_tighten_collapses_a_cofactor_chain_snugly():
    # v→w→d with d on a long backbone (rank 3). The chain should collapse so w
    # is adjacent to d and v adjacent to w — not pinned one-hop from the source.
    dag = nx.DiGraph([("a", "b"), ("b", "c"), ("c", "d"), ("v", "w"), ("w", "d")])
    tight = tighten_ranks(dag, rank_nodes(dag))
    assert tight["w"] == 2          # min(rank d = 3) - 1
    assert tight["v"] == 1          # min(tight w = 2) - 1, using the tightened succ


def test_tighten_respects_earliest_consumer():
    # A source feeding both an early node (rank 1) and a late node can't move
    # past its EARLIEST consumer, so it stays put.
    dag = nx.DiGraph([("s", "a"), ("a", "z"), ("s", "z")])
    tight = tighten_ranks(dag, rank_nodes(dag))
    assert tight["s"] == 0          # min(rank a = 1, ...) - 1 = 0


def test_tighten_never_moves_left_and_keeps_nodes_left_of_successors():
    dag = _feedback_arc_dag(nx.DiGraph([
        ("f12", "f11"), ("f11", "f9"), ("f9", "f10"), ("tf", "f7"),
        ("f7", "f10"), ("f10", "proth"), ("f5", "proth"), ("proth", "thr"),
    ]))
    asap = rank_nodes(dag)
    tight = tighten_ranks(dag, asap)
    for n in dag:
        assert tight[n] >= asap[n]                      # never moves left
        for s in dag.successors(n):
            assert tight[n] < tight[s]                  # strictly left of successors


# --- order_within_ranks -----------------------------------------------------

def _crossings(dag, ranks, order):
    idx = order
    total = 0
    max_rank = max(ranks.values())
    by_rank: dict[int, list[str]] = {}
    for n, r in ranks.items():
        by_rank.setdefault(r, []).append(n)
    for r in range(max_rank):
        edges = sorted(
            (idx[u], idx[v])
            for u in by_rank.get(r, [])
            for v in dag.successors(u)
            if ranks.get(v) == r + 1
        )
        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                if edges[j][1] < edges[i][1]:
                    total += 1
    return total


def test_order_reduces_crossings():
    # Two parallel edges that cross under id-order (a0→b1, a1→b0) should be
    # uncrossed after barycenter sweeps.
    dag = nx.DiGraph([("a0", "b1"), ("a1", "b0")])
    ranks = rank_nodes(dag)
    order = order_within_ranks(dag, ranks)
    assert _crossings(dag, ranks, order) == 0


def test_order_is_deterministic():
    dag = nx.DiGraph([("a", "c"), ("b", "c"), ("c", "d"), ("c", "e")])
    ranks = rank_nodes(dag)
    o1 = order_within_ranks(dag, ranks)
    o2 = order_within_ranks(dag, ranks)
    assert o1 == o2


# --- integration on repro fixtures -----------------------------------------

def test_coagulation_arms_converge_left_to_right():
    fig = load_fixture("coagulation_cascade.json")
    entries = layout_pathway(fig)
    pos = _entity_pos(entries)
    label = {e.id: e.label for e in fig.entities}
    x = {label[i]: p[0] for i, p in pos.items()}
    # Both input arms start left of where they converge on Factor X.
    assert x["Factor XII"] < x["Factor XI"] < x["Factor IX"] < x["Factor X"]
    assert x["Tissue Factor"] < x["Factor VII"] < x["Factor X"]
    # Downstream cascade proceeds strictly rightward.
    assert x["Factor X"] < x["Prothrombin"] < x["Thrombin"] < x["Fibrin clot"]


def test_cofactor_factor_v_sits_beside_prothrombin_not_far_left():
    # LT10: Factor V (no activator) used to pin to column 0 and draw a long edge
    # across the whole figure. Tightening pulls it just left of Prothrombin.
    fig = load_fixture("coagulation_cascade.json")
    pos = _entity_pos(layout_pathway(fig))
    label = {e.id: e.label for e in fig.entities}
    x = {label[i]: p[0] for i, p in pos.items()}
    # Sits to the right of the early intrinsic factors (not stranded at column 0).
    assert x["Factor V"] > x["Factor IX"]
    # And immediately left of the node it modifies — in the same column as the
    # other Prothrombin feeder (Factor X), not arching across the figure.
    assert x["Factor V"] < x["Prothrombin"]
    assert x["Factor V"] == x["Factor X"]


def test_crispr_reads_in_order_without_crossings():
    fig = load_fixture("crispr_cas9.json")
    entries = layout_pathway(fig)
    pos = _entity_pos(entries)
    label = {e.id: e.label for e in fig.entities}
    x = {label[i]: p[0] for i, p in pos.items()}
    # Mechanism reads Cas9 + sgRNA → RNP → PAM → R-loop → DSB.
    assert x["Cas9"] < x["Cas9-sgRNA RNP"]
    assert x["sgRNA"] < x["Cas9-sgRNA RNP"]
    assert (x["Cas9-sgRNA RNP"] < x["PAM site"] < x["R-loop"]
            < x["Double-strand break"])

    # No edge crossings in the laid-out DAG.
    DG = nx.DiGraph()
    for e in fig.entities:
        DG.add_node(e.id)
    for r in fig.relations:
        DG.add_edge(r.source, r.target)
    dag = _feedback_arc_dag(DG)
    ranks = rank_nodes(dag)
    order = order_within_ranks(dag, ranks)
    assert _crossings(dag, ranks, order) == 0
