# Dataset card - IBM AMLSim sample `20K_fanin200cycle200`

* **Source:** https://github.com/IBM/AMLSim -> `sample/20K_fanin200cycle200.tgz` (also `20K_cycle200`, `20K_fanin200`)
  Direct URL used by `scripts/01_download_data.py`: `https://raw.githubusercontent.com/IBM/AMLSim/master/sample/20K_fanin200cycle200.tgz`
* **Nature:** synthetic, produced by the AMLSim multi-agent simulator. Please cite: Suzumura & Kanezashi, *Anti-Money Laundering Datasets*, IBM InPlusLab, 2021 (see the AMLSim README for BibTeX).
* **Contents of the archive:** `transactions.csv`, `nodes.csv`, `metadata.txt` (+ PNG charts). Pattern content: 200 cycles + 200 fan-in.
* Also in the repo: `sample/outputs/*` (accounts/tx/alerts/cash_tx) - only 45 transactions, too small to train on, so not used.

## transactions.csv (120,558 rows)
| Column | Type | Meaning |
|---|---|---|
| sourceNodeId | int | sender account id (matches `nodes.nodeid`) |
| targetNodeId | int | receiver account id |
| value | float | amount; 2.51-599.91, median 252 |
| time | int | simulation step 1-149 (no calendar timestamp) |

**Not available:** transaction ID (we create a synthetic `tx_id`), transaction type/channel, real timestamp, per-transaction fraud label.

## nodes.csv (20,000 rows)
| Column | Type | Meaning |
|---|---|---|
| nodeid | int | account id |
| isFraud | 0/1 | **account-level ground-truth label** - 1,804 fraud (9.02%) |
| init_balance | float | initial balance, 100-600 (similar distribution for fraud/normal) |
| fraudStep | int | step at which the account became fraudulent; -1 for 50.2% of fraud accounts (meaning unclear in the source - not used as a feature) |

## Data quality findings
* No missing values, no non-positive amounts, no unknown account ids.
* 1,684 exact duplicate rows - all between two fraud accounts (simulator repeat transfers). Kept.
* 15 self-transfers (9 fraud-fraud, 6 normal-normal). Kept and flagged.
* 19,980 of 20,000 accounts have at least one transaction.
* Fraud-to-fraud transfers have much lower amounts (median 116.6) than all other transfers (median ~253-299; normal minimum 100.04) - a simulator artifact.
* The fraud accounts form one giant connected component (1,799 of 1,804 accounts), so connected components cannot separate rings; communities are used instead.

## Labels used
* Account label = `isFraud` (ground truth).
* Transaction label (derived proxy) = `sender isFraud AND receiver isFraud` -> 7,885 positives (6.54%).
