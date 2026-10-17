"""Step 2: inspect the real schema, data quality and class balance; write reports/data_profile.md and plots."""
import _bootstrap  # noqa: F401
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from traceguard import config as C
from traceguard import data as D

name = sys.argv[1] if len(sys.argv) > 1 else C.DATASET_NAME
C.REPORTS_DIR.mkdir(exist_ok=True)
nodes_raw, tx_raw = D.load_raw(name)

print("=== nodes.csv ===");        print(nodes_raw.dtypes.to_string()); print(nodes_raw.head(3).to_string())
print("=== transactions.csv ==="); print(tx_raw.dtypes.to_string());    print(tx_raw.head(3).to_string())

nodes, tx, rep = D.clean(nodes_raw, tx_raw)
tx = D.add_tx_label(tx, nodes)
print("\nCleaning report:", rep)

fraud = nodes[C.NODE_LABEL].sum()
print(f"\nFraud accounts: {fraud} / {len(nodes)} ({fraud/len(nodes):.2%})")
print(f"fraudStep == -1 among fraud accounts: {(nodes.loc[nodes[C.NODE_LABEL]==1, C.NODE_FRAUD_STEP]==-1).mean():.1%}")
print(f"Proxy tx_label=1 (both endpoints fraud): {tx['tx_label'].sum()} / {len(tx)} ({tx['tx_label'].mean():.2%})")
print("\nAmount by tx_label:\n", tx.groupby("tx_label")[C.AMT].describe().round(2).to_string())
print("\nAmount by (sender_is_fraud, receiver_is_fraud):\n", tx.groupby(["sender_is_fraud", "receiver_is_fraud"])[C.AMT].agg(["count", "mean", "median"]).round(2).to_string())

out_deg = tx.groupby(C.SRC).size(); in_deg = tx.groupby(C.DST).size()
act = pd.DataFrame({"out": out_deg, "in": in_deg}).reindex(nodes[C.NODE_ID]).fillna(0)
print("\nTransactions per account (out/in):\n", act.describe().round(2).to_string())

# ---- plots
fig, ax = plt.subplots(2, 2, figsize=(11, 8))
ax[0, 0].hist([tx.loc[tx.tx_label == 0, C.AMT], tx.loc[tx.tx_label == 1, C.AMT]], bins=40, label=["normal", "label=1"], density=True)
ax[0, 0].set(title="Amount distribution (density)", xlabel="amount"); ax[0, 0].legend()
tx.groupby(C.TIME).size().plot(ax=ax[0, 1], title="Transactions per time step"); ax[0, 1].set_xlabel("time step")
tx.groupby(C.TIME)["tx_label"].mean().plot(ax=ax[1, 0], title="Share of label=1 per time step"); ax[1, 0].set_xlabel("time step")
fa = act.join(nodes.set_index(C.NODE_ID)[C.NODE_LABEL])
ax[1, 1].hist([fa.loc[fa.isFraud == 0, "in"], fa.loc[fa.isFraud == 1, "in"]], bins=30, density=True, label=["normal", "fraud"], log=True)
ax[1, 1].set(title="Incoming tx count per account", xlabel="in-degree"); ax[1, 1].legend()
plt.tight_layout(); plt.savefig(C.REPORTS_DIR / "eda_overview.png", dpi=120)

with open(C.REPORTS_DIR / "data_profile.md", "w", encoding="utf-8") as f:
    f.write(f"# Data profile - {name}\n\nSource: IBM AMLSim `sample/{name}.tgz` (synthetic data).\n\n")
    f.write(f"- accounts: {len(nodes)} ({fraud} fraud = {fraud/len(nodes):.2%})\n- transactions: {len(tx)}, time steps {tx[C.TIME].min()}..{tx[C.TIME].max()}\n")
    f.write(f"- cleaning report: `{rep}`\n- proxy tx label prevalence: {tx['tx_label'].mean():.2%}\n")
print("\nSaved reports/eda_overview.png and reports/data_profile.md")
