"""Correctness tests for the feature code. Run:  python -m pytest -q"""
import numpy as np
import pandas as pd
import pytest

from traceguard import config as C
from traceguard import data as D
from traceguard.features import TX_FEATURES, HistoryStore, build_tx_features


def _toy():
    rows = [  # src, dst, amount, time
        (1, 2, 100.0, 1), (1, 3, 50.0, 1), (2, 3, 70.0, 2), (3, 1, 20.0, 3),
        (1, 2, 100.0, 3), (2, 1, 10.0, 5), (1, 2, 40.0, 9), (4, 2, 60.0, 9),
    ]
    tx = pd.DataFrame(rows, columns=[C.SRC, C.DST, C.AMT, C.TIME])
    nodes = pd.DataFrame({C.NODE_ID: [1, 2, 3, 4], C.NODE_LABEL: [0, 0, 0, 0],
                          C.NODE_BAL: [200.0, 150.0, 120.0, 300.0], C.NODE_FRAUD_STEP: -1})
    return nodes, D.clean(nodes, tx)[1]


def test_known_values():
    nodes, tx = _toy()
    f = build_tx_features(tx, nodes)
    tx = tx.reset_index(drop=True)
    # last-but-one row: 1->2 amount 40 at t=9. Prior 1->2 transfers: t=1 and t=3 -> pair_cnt 2
    i = tx.index[(tx[C.SRC] == 1) & (tx[C.DST] == 2) & (tx[C.TIME] == 9)][0]
    assert f.loc[i, "pair_cnt"] == 2
    assert f.loc[i, "reverse_pair_cnt"] == 1          # 2->1 happened at t=5
    assert f.loc[i, "s_out_cnt"] == 3                 # 1 sent at t=1,1,3 before t=9
    assert f.loc[i, "s_out_uniq"] == 2                # to 2 and 3
    # window is [t-7, t) = [2, 9): sender 1 sent only at t=3 inside it
    assert f.loc[i, "s_out_cnt_w"] == 1


def test_same_step_transactions_do_not_see_each_other():
    nodes, tx = _toy()
    f = build_tx_features(tx, nodes)
    first_two = tx.index[tx[C.TIME] == 1]
    assert (f.loc[first_two, "s_out_cnt"] == 0).all()   # both t=1 rows have no strictly-earlier history


def test_no_future_leakage():
    """Features of earlier transactions must not change when future transactions change."""
    nodes, tx = _toy()
    base = build_tx_features(tx, nodes)
    mod = tx.copy()
    late = mod[C.TIME] >= 9
    mod.loc[late, C.AMT] = mod.loc[late, C.AMT] * 1000
    mod = pd.concat([mod, pd.DataFrame({"tx_id": [99], C.SRC: [1], C.DST: [4], C.AMT: [9999.0], C.TIME: [50], "is_self_transfer": [0]})],
                    ignore_index=True)
    after = build_tx_features(mod, nodes).iloc[: len(tx)]
    early = (tx[C.TIME] < 9).to_numpy()
    pd.testing.assert_frame_equal(base[early].reset_index(drop=True), after[early].reset_index(drop=True))


def test_batch_equals_online_on_real_data():
    """The vectorised training features and the live-scoring features must be identical."""
    try:
        nodes, tx = D.load_raw()
    except FileNotFoundError:
        pytest.skip("run scripts/01_download_data.py first")
    nodes, tx, _ = D.clean(nodes, tx)
    tx = tx[tx[C.TIME] <= 40].reset_index(drop=True)
    batch = build_tx_features(tx, nodes)
    bal = nodes.set_index(C.NODE_ID)[C.NODE_BAL]
    rng = np.random.default_rng(0)
    for i in rng.choice(len(tx), 150, replace=False):
        r = tx.iloc[i]
        store = HistoryStore.from_dataframe(tx[tx[C.TIME] < r[C.TIME]])      # only the strict past
        live = store.features(int(r[C.SRC]), int(r[C.DST]), float(r[C.AMT]), int(r[C.TIME]), float(bal[r[C.SRC]]))
        np.testing.assert_allclose(live[TX_FEATURES].to_numpy(dtype=float), batch.iloc[[i]][TX_FEATURES].to_numpy(dtype=float),
                                   rtol=1e-9, atol=1e-9, equal_nan=True)


def test_clean_removes_invalid_rows():
    nodes = pd.DataFrame({C.NODE_ID: [1, 2], C.NODE_LABEL: [0, 1], C.NODE_BAL: [10.0, 20.0], C.NODE_FRAUD_STEP: [-1, 3]})
    tx = pd.DataFrame({C.SRC: [1, 1, 1, 9], C.DST: [2, 2, 2, 2], C.AMT: [5.0, -1.0, np.nan, 3.0], C.TIME: [1, 1, 1, 1]})
    _, out, rep = D.clean(nodes, tx)
    assert len(out) == 1
    assert rep["dropped_nonpositive_amount"] == 1 and rep["dropped_missing"] == 1 and rep["dropped_unknown_account"] == 1
