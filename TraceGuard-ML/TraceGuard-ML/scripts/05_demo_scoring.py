"""Step 4: demo of the integration layer - score live transactions the way the FastAPI backend would."""
import _bootstrap  # noqa: F401
import json

import numpy as np
import pandas as pd

from traceguard import config as C
from traceguard import data as D
from traceguard.inference import TraceGuardScorer

# history = everything up to the end of the validation period; replay a few later transactions
scorer = TraceGuardScorer.from_dataset(up_to_step=C.TX_VAL_END)
nodes, tx, _ = D.clean(*D.load_raw())
tx = D.add_tx_label(tx, nodes)
live = tx[tx[C.TIME] > C.TX_VAL_END]
sample = pd.concat([live[live.tx_label == 1].sample(3, random_state=1), live[live.tx_label == 0].sample(3, random_state=1)])

for _, r in sample.sort_values(C.TIME).iterrows():
    req = {"transaction_id": f"TX-{int(r.tx_id)}", "sender_account_id": int(r[C.SRC]), "receiver_account_id": int(r[C.DST]),
           "amount": float(r[C.AMT]), "step": int(r[C.TIME])}
    res = scorer.score(req)
    print(f"proxy-label={int(r.tx_label)}  ->  {res.risk_level:<6} score={res.risk_score:.3f} action={res.recommended_action:<6} "
          f"reasons={[x.code for x in res.reasons]} ({res.latency_ms} ms)")
print("\nExample full JSON response:\n", json.dumps(scorer.score(req).model_dump(), indent=2))

lat = []
for _, r in live.head(300).iterrows():
    lat.append(scorer.score({"sender_account_id": int(r[C.SRC]), "receiver_account_id": int(r[C.DST]),
                             "amount": float(r[C.AMT]), "step": int(r[C.TIME])}).latency_ms)
print(f"\nLatency over 300 calls: median={np.median(lat):.1f} ms, p95={np.percentile(lat, 95):.1f} ms")
