"""Suspicious-network (money-mule ring) discovery and ego-networks for the dashboard.

NOTE on AMLSim: the true fraud accounts form ONE giant connected blob (patterns overlap),
so plain connected components cannot separate rings. We therefore split the flagged
subgraph into communities (Louvain) and report each community as a candidate network.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from . import config as C


def find_suspicious_networks(tx: pd.DataFrame, account_score: pd.Series, threshold: float,
                             min_size: int = 3, seed: int = C.RANDOM_STATE) -> list[dict]:
    flagged = set(account_score.index[account_score >= threshold])
    e = tx[tx[C.SRC].isin(flagged) & tx[C.DST].isin(flagged) & (tx[C.SRC] != tx[C.DST])]
    if e.empty:
        return []
    agg = e.groupby([C.SRC, C.DST])[C.AMT].agg(n="count", amount="sum").reset_index()
    dg = nx.DiGraph()
    for s, d, n, a in agg.itertuples(index=False):
        dg.add_edge(int(s), int(d), n=int(n), amount=float(a))
    ug = nx.Graph()
    for s, d, data in dg.edges(data=True):
        w = data["n"] + (ug[s][d]["weight"] if ug.has_edge(s, d) else 0)
        ug.add_edge(s, d, weight=w)

    nets = []
    for comm in nx.community.louvain_communities(ug, weight="weight", seed=seed):
        if len(comm) < min_size:
            continue
        sub = dg.subgraph(comm)
        if sub.number_of_edges() == 0:
            continue
        has_cycle = any(len(c) > 1 for c in nx.strongly_connected_components(sub))
        indeg = {n: sub.in_degree(n) for n in sub}
        hub = max(indeg, key=indeg.get)
        pattern = "cycle" if has_cycle else ("fan-in" if indeg[hub] >= 3 else "chain/other")
        nets.append({
            "accounts": sorted(int(a) for a in comm), "n_accounts": len(comm),
            "n_transactions": int(sum(d["n"] for *_, d in sub.edges(data=True))),
            "total_amount": round(sum(d["amount"] for *_, d in sub.edges(data=True)), 2),
            "mean_account_score": round(float(account_score.loc[list(comm)].mean()), 4),
            "pattern_hint": pattern, "hub_account": int(hub), "hub_in_degree": int(indeg[hub]),
        })
    nets.sort(key=lambda n: (-n["mean_account_score"], -n["n_accounts"]))
    for i, n in enumerate(nets, 1):
        n["network_id"] = f"NET-{i:04d}"
    return nets


def ego_network(tx: pd.DataFrame, account: int, account_score: pd.Series | None = None, hops: int = 2, max_nodes: int = 60) -> dict:
    """Nodes/edges within `hops` of `account` (undirected reach, directed edges) - ready for a graph widget."""
    nodes = {account}
    frontier = {account}
    for _ in range(hops):
        m = tx[tx[C.SRC].isin(frontier) | tx[C.DST].isin(frontier)]
        nxt = (set(m[C.SRC]) | set(m[C.DST])) - nodes
        if len(nodes) + len(nxt) > max_nodes:       # keep the picture readable
            nxt = set(sorted(nxt)[: max(0, max_nodes - len(nodes))])
        nodes |= nxt
        frontier = nxt
        if not frontier:
            break
    e = tx[tx[C.SRC].isin(nodes) & tx[C.DST].isin(nodes)]
    agg = e.groupby([C.SRC, C.DST])[C.AMT].agg(tx_count="count", total_amount="sum").reset_index()
    return {
        "center": int(account),
        "nodes": [{"id": int(n), "risk_score": None if account_score is None or n not in account_score.index else round(float(account_score.loc[n]), 4)} for n in sorted(nodes)],
        "edges": [{"source": int(s), "target": int(d), "tx_count": int(c), "total_amount": round(float(a), 2)} for s, d, c, a in agg.itertuples(index=False)],
    }
