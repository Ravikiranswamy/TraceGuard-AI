"""Central configuration: paths, dataset location, column names, split rules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

# --- Dataset (IBM AMLSim, sample archives shipped inside the GitHub repo) ---
DATASET_NAME = "20K_fanin200cycle200"   # also available: 20K_cycle200, 20K_fanin200
DATASET_URL = "https://raw.githubusercontent.com/IBM/AMLSim/master/sample/{name}.tgz"

# --- Verified schema of the AMLSim sample files ---
# transactions.csv : sourceNodeId, targetNodeId, value, time      (no tx id, no tx label)
# nodes.csv        : nodeid, isFraud, init_balance, fraudStep     (label is per ACCOUNT)
SRC, DST, AMT, TIME = "sourceNodeId", "targetNodeId", "value", "time"
NODE_ID, NODE_LABEL, NODE_BAL, NODE_FRAUD_STEP = "nodeid", "isFraud", "init_balance", "fraudStep"

RANDOM_STATE = 42

# --- Temporal split for the transaction model (time steps are integers 1..149) ---
TX_TRAIN_END = 100     # train: time <= 100
TX_VAL_END = 120       # val:   100 < time <= 120 ; test: time > 120

# Rolling window (in time steps) for velocity features
WINDOW_STEPS = 7
