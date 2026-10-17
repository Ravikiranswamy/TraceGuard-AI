# TraceGuard-ML

ML component of **TraceGuard AI**: score a transaction *before* it is authorized, and surface likely money-mule accounts and networks.
Built and verified on IBM's synthetic **AMLSim** data. Everything below was actually run; numbers are from `reports/`.

## 1. Setup (Windows / PowerShell, Python 3.11 or 3.12)

```powershell
cd TraceGuard-ML
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked:  Set-ExecutionPolicy -Scope Process Bypass
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
macOS/Linux: `source .venv/bin/activate`. If any command fails, copy the **exact** error and send it - do not change settings blindly.

## 2. Run the pipeline (in order)

```powershell
python scripts\01_download_data.py          # downloads AMLSim sample from GitHub into data\raw\
python scripts\02_inspect_data.py           # schema, quality, class balance -> reports\data_profile.md, eda_overview.png
python scripts\03_train_account_model.py    # account-level mule model + suspicious networks
python scripts\04_train_transaction_model.py# transaction-level pre-authorization model (+ ablations)
python scripts\05_demo_scoring.py           # scores live transactions like the API will
python -m pytest -q                         # 9 tests (feature correctness, no-leakage, API contract)
```
The whole pipeline should take a few minutes on a laptop. Other datasets: `python scripts\01_download_data.py 20K_cycle200` then pass the same name as an argument to scripts 02-04.

## 3. What is in the data (verified, see DATASET.md)

* Source: `IBM/AMLSim` -> `sample/20K_fanin200cycle200.tgz` (synthetic; 20,000 accounts, 120,558 transactions, 149 time steps).
* `transactions.csv`: `sourceNodeId, targetNodeId, value, time` - **no transaction ID, no per-transaction label**.
* `nodes.csv`: `nodeid, isFraud, init_balance, fraudStep` - **labels exist only per account** (1,804 fraud = 9.0%).
* So: labelled supervised learning is possible at **account level**. For transactions we use a **proxy label**
  (`tx_label = 1` when sender AND receiver are both fraud accounts - 6.5% of transactions). This is a modelling choice, not ground truth.

## 4. Results (held-out test data; thresholds chosen on validation only)

**Account model** (stratified 60/20/20 split by account; 4,000 test accounts, 361 fraud)

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Random scorer | 0.090 | 0.5 | - | - | - |
| IsolationForest (unsupervised) | 0.451 | 0.841 | 0.623 | 0.443 | 0.518 |
| Logistic regression | 0.793 | 0.887 | 0.969 | 0.704 | 0.815 |
| **Gradient boosting** | **0.815** | **0.910** | 0.963 | 0.720 | **0.824** |

**Transaction model** (temporal split: train t<=100, validation 101-120, test >120; 11,190 test tx, 1,093 positive)

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Random scorer | 0.098 | 0.5 | - | - | - |
| IsolationForest (unsupervised) | 0.331 | 0.854 | 0.378 | 0.809 | 0.515 |
| Logistic regression | 0.873 | 0.957 | 0.939 | 0.703 | 0.804 |
| **Gradient boosting (shipped)** | **0.886** | **0.959** | 0.932 | 0.739 | **0.824** |
| ablation: amount features only | 0.817 | 0.911 | 0.904 | 0.679 | 0.775 |
| ablation: history features only | 0.735 | 0.900 | 0.704 | 0.613 | 0.655 |

Risk tiers on test: **HIGH** (score >= 0.879): precision 0.93, recall 0.74, flags 7.7% of tx.
**MEDIUM+** (score >= 0.605): precision 0.52, recall 0.88, flags 16.5% of tx.

Suspicious networks (out-of-fold account scores, Louvain communities): 52 networks, 1,352 accounts, 94.8% of them truly fraud,
covering 71% of all fraud accounts. Replicated on the other two AMLSim samples (PR-AUC 0.75-0.89, see section 6).

## 5. Read these caveats before showing results to anyone

1. **Synthetic data.** Scores here say the pipeline works; they do **not** predict real-bank performance.
2. **Amount artifact.** In AMLSim, normal transfers are 100-600 while laundering transfers go as low as 2.5. The *amount-only*
   ablation already reaches PR-AUC 0.817, and `amount` is the top feature. Real banks will not have this gap. The history-only
   ablation (0.735 vs 0.098 random) shows the behavioural features carry real signal on their own.
3. **Proxy transaction label** (see section 3).
4. **Account model uses whole-history features** - fine for offline ranking of accounts/networks, not for real-time scoring. Real-time scoring uses the transaction model, which only sees the past (tested: `tests/test_features.py`).
5. **Exact duplicate rows (1,684)** are all fraud-to-fraud repeats created by the simulator; kept, not removed.
6. **Reason codes are rules, not model explanations.** Only rules with measurable lift were kept; a MEDIUM score can have an empty reason list.
7. Each number is from a single run with a fixed seed (reproducible, but no confidence intervals yet); multi-seed averages are a sensible next step.

## 6. Robustness on the other AMLSim samples (same code, gradient boosting, test)

| Dataset | Account PR-AUC / F1 | Transaction PR-AUC / F1 | Tx history-only PR-AUC |
|---|---|---|---|
| 20K_fanin200cycle200 (main) | 0.815 / 0.824 | 0.886 / 0.824 | 0.735 |
| 20K_cycle200 | 0.769 / 0.780 | 0.864 / 0.828 | 0.580 |
| 20K_fanin200 | 0.746 / 0.803 | 0.887 / 0.872 | 0.794 |

## 7. Project layout

```
traceguard/   config.py data.py features.py models.py evaluate.py networks.py schemas.py inference.py
scripts/      01..05 numbered steps          tests/       pytest suite
api_example/  main.py  (FastAPI reference)   models/      trained .joblib files   reports/  metrics, plots, scored data
DATASET.md    data card                      INTEGRATION.md   API contract for Friend 2
```

## 8. Next steps (suggested)

* Replace the amount-driven signal: add features that survive real data (time-of-day, device, channel, geography) once the team has them.
* Graph features at transaction time (2-3 hop cycle closure, neighbour risk) and a GNN comparison.
* Try the larger AMLSim runs / IBM's newer AML datasets to validate beyond this one sample.
* Calibrate scores and agree the HOLD/REVIEW policy with the product owner (thresholds are in the model file).
