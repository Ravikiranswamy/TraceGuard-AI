"""Dataset download, loading, validation and cleaning."""
from __future__ import annotations

import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


def download_dataset(name: str = C.DATASET_NAME, dest: Path = C.DATA_RAW) -> Path:
    """Download the AMLSim sample archive from GitHub and extract it. Returns folder with the CSVs."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out_dir = dest / name
    if (out_dir / "transactions.csv").exists() and (out_dir / "nodes.csv").exists():
        return out_dir
    url = C.DATASET_URL.format(name=name)
    archive = dest / f"{name}.tgz"
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, archive)
    with tarfile.open(archive, "r:gz") as tar:
        # the archive contains a top-level folder named like the dataset
        try:
            tar.extractall(dest, filter="data")      # Python >= 3.11.4 (safe extraction)
        except TypeError:
            tar.extractall(dest)                     # older 3.11.x without `filter`
    if not (out_dir / "transactions.csv").exists():
        raise FileNotFoundError(f"transactions.csv not found under {out_dir} after extraction")
    return out_dir


def load_raw(name: str = C.DATASET_NAME, base: Path = C.DATA_RAW) -> tuple[pd.DataFrame, pd.DataFrame]:
    folder = Path(base) / name
    nodes = pd.read_csv(folder / "nodes.csv")
    tx = pd.read_csv(folder / "transactions.csv")
    return nodes, tx


def check_schema(nodes: pd.DataFrame, tx: pd.DataFrame) -> None:
    """Fail loudly if the real files do not look like what the code expects."""
    need_tx = {C.SRC, C.DST, C.AMT, C.TIME}
    need_nodes = {C.NODE_ID, C.NODE_LABEL, C.NODE_BAL, C.NODE_FRAUD_STEP}
    if not need_tx <= set(tx.columns):
        raise ValueError(f"transactions.csv missing {need_tx - set(tx.columns)}; has {list(tx.columns)}")
    if not need_nodes <= set(nodes.columns):
        raise ValueError(f"nodes.csv missing {need_nodes - set(nodes.columns)}; has {list(nodes.columns)}")


def clean(nodes: pd.DataFrame, tx: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Validate and clean. Returns (nodes, tx, report).

    Rules (every removal is counted in the report):
      * drop rows with missing values
      * drop transactions with non-positive amount
      * drop transactions whose sender/receiver is not in nodes.csv
    Kept on purpose (flagged / reported only):
      * exact duplicate rows - in this dataset they are simulator repeat-transfers, not errors
      * self-transfers - flagged with `is_self_transfer`
    A synthetic `tx_id` is added (the dataset has none): row order after sorting by time.
    """
    check_schema(nodes, tx)
    report: dict = {"rows_in": int(len(tx)), "nodes_in": int(len(nodes))}

    nodes = nodes.drop_duplicates(C.NODE_ID).dropna(subset=[C.NODE_ID, C.NODE_LABEL]).copy()
    nodes[C.NODE_BAL] = nodes[C.NODE_BAL].fillna(nodes[C.NODE_BAL].median())

    tx = tx[[C.SRC, C.DST, C.AMT, C.TIME]].copy()
    n0 = len(tx)
    tx = tx.dropna()
    report["dropped_missing"] = int(n0 - len(tx))

    n0 = len(tx)
    tx = tx[tx[C.AMT] > 0]
    report["dropped_nonpositive_amount"] = int(n0 - len(tx))

    known = set(nodes[C.NODE_ID])
    n0 = len(tx)
    tx = tx[tx[C.SRC].isin(known) & tx[C.DST].isin(known)]
    report["dropped_unknown_account"] = int(n0 - len(tx))

    tx = tx.astype({C.SRC: "int64", C.DST: "int64", C.TIME: "int64", C.AMT: "float64"})
    report["exact_duplicates_kept"] = int(tx.duplicated().sum())
    tx["is_self_transfer"] = (tx[C.SRC] == tx[C.DST]).astype("int8")
    report["self_transfers_kept"] = int(tx["is_self_transfer"].sum())

    tx = tx.sort_values([C.TIME, C.SRC, C.DST, C.AMT], kind="mergesort").reset_index(drop=True)
    tx.insert(0, "tx_id", np.arange(len(tx), dtype="int64"))
    report["rows_out"] = int(len(tx))
    return nodes.reset_index(drop=True), tx, report


def add_tx_label(tx: pd.DataFrame, nodes: pd.DataFrame) -> pd.DataFrame:
    """Derived PROXY label (AMLSim has no per-transaction label).

    tx_label = 1 when BOTH sender and receiver are fraud accounts, i.e. money moving
    inside the laundering group. Transfers between a normal and a fraud account look
    like ordinary background activity and are labelled 0.
    """
    fraud = nodes.set_index(C.NODE_ID)[C.NODE_LABEL]
    out = tx.copy()
    out["sender_is_fraud"] = out[C.SRC].map(fraud).astype("int8")
    out["receiver_is_fraud"] = out[C.DST].map(fraud).astype("int8")
    out["tx_label"] = (out["sender_is_fraud"] & out["receiver_is_fraud"]).astype("int8")
    return out


def temporal_split(tx: pd.DataFrame) -> dict[str, pd.DataFrame]:
    t = tx[C.TIME]
    return {
        "train": tx[t <= C.TX_TRAIN_END],
        "val": tx[(t > C.TX_TRAIN_END) & (t <= C.TX_VAL_END)],
        "test": tx[t > C.TX_VAL_END],
    }
