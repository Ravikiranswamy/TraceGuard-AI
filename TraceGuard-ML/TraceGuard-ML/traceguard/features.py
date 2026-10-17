"""Feature engineering.

Two feature sets:

1. TRANSACTION features (point-in-time, used for pre-authorization scoring)
   Every feature of a transaction at time t uses ONLY transactions with time < t.
   Two implementations that must agree (checked in tests/test_features.py):
     * build_tx_features(...)   - vectorised, for training/evaluation on a whole table
     * HistoryStore.features(...) - incremental, for scoring ONE live transaction

2. ACCOUNT features (whole-history graph/behaviour profile, used for mule-account ranking
   and for finding suspicious networks offline).
"""
from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from . import config as C

# ----------------------------------------------------------------------------
# Transaction features
# ----------------------------------------------------------------------------
_ROLE_BASE = ["out_cnt", "out_amt", "out_uniq", "in_cnt", "in_amt", "in_uniq", "out_cnt_w", "in_cnt_w"]

TX_FEATURES = (
    ["amount", "log_amount", "amt_to_sender_balance", "amt_vs_sender_avg_out", "amt_vs_receiver_avg_in",
     "pair_cnt", "reverse_pair_cnt", "is_new_pair", "is_self_transfer"]
    + [f"s_{c}" for c in _ROLE_BASE] + [f"r_{c}" for c in _ROLE_BASE]
    + ["s_pass_ratio", "r_pass_ratio", "r_fanin_ratio"]
)


def _lookup(events: pd.DataFrame, key: str, cols: list[str], keys: np.ndarray, times: np.ndarray) -> pd.DataFrame:
    """For each (key, time) query return the cumulative sum of `cols` over events of that key
    with event time STRICTLY LESS than the query time (0 when there are none)."""
    g = events.groupby([key, "time"], as_index=False)[cols].sum().sort_values("time", kind="mergesort")
    g[cols] = g.groupby(key)[cols].cumsum()
    q = pd.DataFrame({key: keys, "time": times, "_pos": np.arange(len(keys))}).sort_values("time", kind="mergesort")
    m = pd.merge_asof(q, g, on="time", by=key, allow_exact_matches=False).sort_values("_pos")
    return m[cols].fillna(0.0).reset_index(drop=True)


def build_tx_features(tx: pd.DataFrame, nodes: pd.DataFrame | None = None, window: int = C.WINDOW_STEPS) -> pd.DataFrame:
    """Vectorised point-in-time features for every row of `tx` (history = the rows of `tx` itself)."""
    tx = tx.reset_index(drop=True)
    src, dst = tx[C.SRC].to_numpy(), tx[C.DST].to_numpy()
    amt, t = tx[C.AMT].to_numpy(dtype=float), tx[C.TIME].to_numpy()
    n = len(tx)

    out_ev = pd.DataFrame({"acc": src, "time": t, "out_cnt": 1.0, "out_amt": amt})
    in_ev = pd.DataFrame({"acc": dst, "time": t, "in_cnt": 1.0, "in_amt": amt})
    first = tx.groupby([C.SRC, C.DST], as_index=False)[C.TIME].min().rename(columns={C.TIME: "time"})
    out_uq = pd.DataFrame({"acc": first[C.SRC].to_numpy(), "time": first["time"].to_numpy(), "out_uniq": 1.0})
    in_uq = pd.DataFrame({"acc": first[C.DST].to_numpy(), "time": first["time"].to_numpy(), "in_uniq": 1.0})

    def role(acc: np.ndarray) -> pd.DataFrame:
        parts = [
            _lookup(out_ev, "acc", ["out_cnt", "out_amt"], acc, t),
            _lookup(in_ev, "acc", ["in_cnt", "in_amt"], acc, t),
            _lookup(out_uq, "acc", ["out_uniq"], acc, t),
            _lookup(in_uq, "acc", ["in_uniq"], acc, t),
        ]
        cur = pd.concat(parts, axis=1)
        # velocity: events inside [t-window, t)
        past = pd.concat([
            _lookup(out_ev, "acc", ["out_cnt"], acc, t - window),
            _lookup(in_ev, "acc", ["in_cnt"], acc, t - window),
        ], axis=1)
        cur["out_cnt_w"] = cur["out_cnt"] - past["out_cnt"]
        cur["in_cnt_w"] = cur["in_cnt"] - past["in_cnt"]
        return cur[_ROLE_BASE]

    s, r = role(src).add_prefix("s_"), role(dst).add_prefix("r_")

    big = int(max(src.max(), dst.max())) + 1
    pair_ev = pd.DataFrame({"acc": src.astype("int64") * big + dst, "time": t, "pair_cnt": 1.0})
    pc = _lookup(pair_ev, "acc", ["pair_cnt"], pair_ev["acc"].to_numpy(), t)["pair_cnt"]
    rev_keys = dst.astype("int64") * big + src
    rc = _lookup(pair_ev, "acc", ["pair_cnt"], rev_keys, t)["pair_cnt"].rename("reverse_pair_cnt")

    f = pd.concat([s, r], axis=1)
    f["pair_cnt"], f["reverse_pair_cnt"] = pc.to_numpy(), rc.to_numpy()
    f["is_new_pair"] = (f["pair_cnt"] == 0).astype("int8")
    f["amount"] = amt
    f["log_amount"] = np.log1p(amt)
    f["is_self_transfer"] = (src == dst).astype("int8")
    _derived(f, balance=_sender_balance(tx, nodes))
    return f[TX_FEATURES]


def _sender_balance(tx: pd.DataFrame, nodes: pd.DataFrame | None) -> np.ndarray | None:
    if nodes is None:
        return None
    bal = nodes.set_index(C.NODE_ID)[C.NODE_BAL]
    return tx[C.SRC].map(bal).to_numpy(dtype=float)


def _derived(f: pd.DataFrame, balance: np.ndarray | None) -> None:
    """Ratios shared by the batch and online implementations."""
    with np.errstate(divide="ignore", invalid="ignore"):
        s_avg = np.where(f["s_out_cnt"] > 0, f["s_out_amt"] / f["s_out_cnt"], np.nan)
        r_avg = np.where(f["r_in_cnt"] > 0, f["r_in_amt"] / f["r_in_cnt"], np.nan)
        f["amt_vs_sender_avg_out"] = f["amount"] / s_avg          # NaN when no history (model handles NaN)
        f["amt_vs_receiver_avg_in"] = f["amount"] / r_avg
        f["amt_to_sender_balance"] = f["amount"] / balance if balance is not None else np.nan
    f["s_pass_ratio"] = f["s_out_amt"] / (f["s_in_amt"] + 1.0)
    f["r_pass_ratio"] = f["r_out_amt"] / (f["r_in_amt"] + 1.0)
    f["r_fanin_ratio"] = f["r_in_uniq"] / (f["r_out_uniq"] + 1.0)


class HistoryStore:
    """Incremental transaction history for live scoring (same features as build_tx_features).

    Usage in the API:
        store = HistoryStore.from_dataframe(history_df)   # once, at startup
        feats = store.features(sender, receiver, amount, step, sender_balance)
        ...score...
        store.add(sender, receiver, amount, step)          # AFTER the transaction is processed
    `add` expects steps to be non-decreasing (a live stream).
    """

    def __init__(self, window: int = C.WINDOW_STEPS):
        self.window = window
        self.out = defaultdict(lambda: ([], [], []))   # acc -> (times, amounts, counterparties)
        self.inc = defaultdict(lambda: ([], [], []))
        self.pairs = defaultdict(list)                 # (s, r) -> times

    @classmethod
    def from_dataframe(cls, tx: pd.DataFrame, window: int = C.WINDOW_STEPS) -> "HistoryStore":
        store = cls(window)
        for s, d, a, t in tx.sort_values(C.TIME, kind="mergesort")[[C.SRC, C.DST, C.AMT, C.TIME]].itertuples(index=False):
            store.add(int(s), int(d), float(a), int(t))
        return store

    def add(self, s: int, r: int, amount: float, step: int) -> None:
        for book, acc, cp in ((self.out, s, r), (self.inc, r, s)):
            ts, am, cps = book[acc]
            ts.append(step); am.append(amount); cps.append(cp)
        self.pairs[(s, r)].append(step)

    def _role(self, acc: int, t: int) -> dict:
        o_t, o_a, o_c = self.out[acc] if acc in self.out else ([], [], [])
        i_t, i_a, i_c = self.inc[acc] if acc in self.inc else ([], [], [])
        io, ii = bisect_left(o_t, t), bisect_left(i_t, t)
        wo, wi = bisect_left(o_t, t - self.window), bisect_left(i_t, t - self.window)
        return {
            "out_cnt": float(io), "out_amt": float(sum(o_a[:io])), "out_uniq": float(len(set(o_c[:io]))),
            "in_cnt": float(ii), "in_amt": float(sum(i_a[:ii])), "in_uniq": float(len(set(i_c[:ii]))),
            "out_cnt_w": float(io - wo), "in_cnt_w": float(ii - wi),
        }

    def features(self, sender: int, receiver: int, amount: float, step: int,
                 sender_balance: float | None = None) -> pd.DataFrame:
        row = {f"s_{k}": v for k, v in self._role(sender, step).items()}
        row.update({f"r_{k}": v for k, v in self._role(receiver, step).items()})
        row["pair_cnt"] = float(bisect_left(self.pairs.get((sender, receiver), []), step))
        row["reverse_pair_cnt"] = float(bisect_left(self.pairs.get((receiver, sender), []), step))
        row["is_new_pair"] = int(row["pair_cnt"] == 0)
        row["amount"] = float(amount)
        row["log_amount"] = float(np.log1p(amount))
        row["is_self_transfer"] = int(sender == receiver)
        f = pd.DataFrame([row])
        _derived(f, balance=None if sender_balance is None else np.array([float(sender_balance)]))
        return f[TX_FEATURES]

    def is_known(self, acc: int) -> bool:
        return acc in self.out or acc in self.inc


# ----------------------------------------------------------------------------
# Account features (whole-history profile)
# ----------------------------------------------------------------------------
def build_account_features(nodes: pd.DataFrame, tx: pd.DataFrame) -> pd.DataFrame:
    """One row per account, indexed by account id. Uses NO labels (no leakage from isFraud)."""
    ids = nodes[C.NODE_ID].to_numpy()
    base = pd.DataFrame(index=pd.Index(ids, name="account_id"))

    o = tx.groupby(C.SRC)[C.AMT].agg(out_cnt="count", out_amt="sum", out_mean="mean", out_std="std", out_max="max", out_min="min")
    i = tx.groupby(C.DST)[C.AMT].agg(in_cnt="count", in_amt="sum", in_mean="mean", in_std="std", in_max="max", in_min="min")
    ou = tx.groupby(C.SRC)[C.DST].nunique().rename("out_uniq")
    iu = tx.groupby(C.DST)[C.SRC].nunique().rename("in_uniq")
    f = base.join([o, i, ou, iu]).fillna(0.0)

    f["total_cnt"] = f["out_cnt"] + f["in_cnt"]
    f["fanin_ratio"] = f["in_uniq"] / (f["out_uniq"] + 1)
    f["fanout_ratio"] = f["out_uniq"] / (f["in_uniq"] + 1)
    f["pass_through"] = np.minimum(f["in_amt"], f["out_amt"]) / (np.maximum(f["in_amt"], f["out_amt"]) + 1e-9)
    f["in_out_amt_ratio"] = f["in_amt"] / (f["out_amt"] + 1.0)
    f["small_tx_share"] = tx.assign(small=(tx[C.AMT] < 50)).groupby(C.SRC)["small"].mean().reindex(f.index).fillna(0.0)

    # activity over time
    ev = pd.concat([tx[[C.SRC, C.TIME]].rename(columns={C.SRC: "acc"}), tx[[C.DST, C.TIME]].rename(columns={C.DST: "acc"})])
    act = ev.groupby("acc")[C.TIME].agg(first_step="min", last_step="max", active_steps="nunique")
    f = f.join(act).fillna(0.0)
    f["tx_per_active_step"] = f["total_cnt"] / f["active_steps"].clip(lower=1)

    # repetition / reciprocity
    pc = tx.groupby([C.SRC, C.DST]).size().rename("n").reset_index()
    f["max_pair_repeat"] = pc.groupby(C.SRC)["n"].max().reindex(f.index).fillna(0.0)
    rev = pc.rename(columns={C.SRC: C.DST, C.DST: C.SRC})
    recip = pc.merge(rev, on=[C.SRC, C.DST])
    f["reciprocal_partners"] = recip.groupby(C.SRC).size().reindex(f.index).fillna(0.0)
    f["self_transfers"] = tx[tx[C.SRC] == tx[C.DST]].groupby(C.SRC).size().reindex(f.index).fillna(0.0)

    # graph structure: size of the strongly / weakly connected component (cycle & ring indicator)
    pos = {a: k for k, a in enumerate(ids)}
    r_ = tx[C.SRC].map(pos).to_numpy(); c_ = tx[C.DST].map(pos).to_numpy()
    adj = coo_matrix((np.ones(len(r_)), (r_, c_)), shape=(len(ids), len(ids))).tocsr()
    for conn, name in (("strong", "scc_size"), ("weak", "wcc_size")):
        _, lab = connected_components(adj, directed=True, connection=conn)
        sizes = np.bincount(lab)
        f[name] = sizes[lab]
    f["in_cycle"] = (f["scc_size"] > 1).astype("int8")

    f["init_balance"] = nodes.set_index(C.NODE_ID)[C.NODE_BAL].reindex(f.index).to_numpy()
    return f


ACCOUNT_FEATURES_EXCLUDE: list[str] = []   # nothing label-derived is ever computed above
