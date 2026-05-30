"""Layered (Sugiyama-style) layout primitives for compartment-free DAGs.

`pathway_layout._graph_positions` uses this when a figure has no real
compartments (a single implicit band): instead of spring-x ordering + flat
sibling spread, nodes are ranked by longest-path depth (x columns) and
ordered within each rank to minimise edge crossings (y position).

Both functions are pure and deterministic — ties break by node id — so the
same DAG always produces the same layout.
"""
from __future__ import annotations

import networkx as nx


def rank_nodes(dag: nx.DiGraph) -> dict[str, int]:
    """Map each node to its longest-path depth from a source.

    Uses ``nx.topological_generations``: a node's generation index equals
    ``1 + max(rank of its predecessors)`` (0 if it has none), which is
    exactly the longest-path-from-source depth. Convergent inputs therefore
    land in distinct left columns funnelling into the consumer; divergent
    outputs fan out to the right.

    The caller must pass an acyclic graph (e.g. the output of
    ``_feedback_arc_dag``).
    """
    ranks: dict[str, int] = {}
    for depth, generation in enumerate(nx.topological_generations(dag)):
        for node in generation:
            ranks[node] = depth
    return ranks


def tighten_ranks(dag: nx.DiGraph, ranks: dict[str, int]) -> dict[str, int]:
    """Pull slack nodes rightward toward their earliest consumer (LT10).

    ``rank_nodes`` is *as-soon-as-possible* (longest-path-from-source), so a
    node with no predecessors lands in column 0 even when the only thing it
    feeds sits many columns to the right — e.g. the coagulation cofactor
    Factor V (no activator) feeding Prothrombin, which draws one long edge
    across the whole figure. This applies the *as-late-as-possible* schedule:
    each node is pushed to ``min(rank of its successors) − 1`` so it sits
    immediately left of its earliest consumer.

    Computed in reverse topological order using the *already-tightened*
    successor ranks, so a chain of cofactors collapses snugly against the node
    it modifies rather than one hop at a time. Sinks (no successors) keep their
    ``rank_nodes`` value — nothing pulls them. The result never moves a node
    left of its ASAP rank and keeps every node strictly left of its
    successors, so the converged backbone (zero-slack critical path) is
    unchanged and topological order is preserved.

    Pure and deterministic; the caller must pass the same acyclic graph used
    for ``rank_nodes``.
    """
    tightened = dict(ranks)
    for node in reversed(list(nx.topological_sort(dag))):
        successors = list(dag.successors(node))
        if successors:
            tightened[node] = min(tightened[s] for s in successors) - 1
    return tightened


def order_within_ranks(
    dag: nx.DiGraph,
    ranks: dict[str, int],
    *,
    sweeps: int = 4,
) -> dict[str, int]:
    """Order nodes within each rank to reduce edge crossings.

    Returns ``{node: order_index}`` where ``order_index`` is the node's
    0-based position within its rank (top to bottom). Initial order is by id;
    then alternating down/up barycenter sweeps reposition each node to the
    median order-index of its neighbours in the adjacent rank. The ordering
    with the fewest crossings across all sweeps is kept.
    """
    by_rank: dict[int, list[str]] = {}
    for node, r in ranks.items():
        by_rank.setdefault(r, []).append(node)
    for r in by_rank:
        by_rank[r].sort()

    if not by_rank:
        return {}

    max_rank = max(by_rank)
    succ: dict[str, list[str]] = {n: sorted(dag.successors(n)) for n in dag}
    pred: dict[str, list[str]] = {n: sorted(dag.predecessors(n)) for n in dag}

    def index_map(order: dict[int, list[str]]) -> dict[str, int]:
        return {n: i for nodes in order.values() for i, n in enumerate(nodes)}

    def crossings(order: dict[int, list[str]]) -> int:
        idx = index_map(order)
        total = 0
        for r in range(max_rank):
            # Edges between rank r and r+1, sorted by upper endpoint position.
            edges = [
                (idx[u], idx[v])
                for u in order.get(r, [])
                for v in succ[u]
                if ranks.get(v) == r + 1
            ]
            edges.sort()
            # Count inversions in the lower endpoints (= crossings).
            for i in range(len(edges)):
                for j in range(i + 1, len(edges)):
                    if edges[j][1] < edges[i][1]:
                        total += 1
        return total

    def barycenter(node: str, neighbours: list[str], idx: dict[str, int]) -> float:
        adj = [idx[n] for n in neighbours if n in idx]
        if not adj:
            return float(idx[node])
        adj.sort()
        mid = len(adj) // 2
        return adj[mid] if len(adj) % 2 else (adj[mid - 1] + adj[mid]) / 2.0

    best = {r: list(nodes) for r, nodes in by_rank.items()}
    best_cross = crossings(best)
    current = {r: list(nodes) for r, nodes in by_rank.items()}

    for s in range(sweeps):
        down = s % 2 == 0
        rank_seq = range(1, max_rank + 1) if down else range(max_rank - 1, -1, -1)
        idx = index_map(current)
        for r in rank_seq:
            neigh = pred if down else succ
            scored = sorted(
                current.get(r, []),
                key=lambda n: (barycenter(n, neigh[n], idx), n),
            )
            current[r] = scored
            idx = index_map(current)
        c = crossings(current)
        if c < best_cross:
            best_cross = c
            best = {r: list(nodes) for r, nodes in current.items()}

    return index_map(best)
