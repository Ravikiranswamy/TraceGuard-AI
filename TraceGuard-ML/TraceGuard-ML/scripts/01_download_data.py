"""Step 1: download the AMLSim sample dataset from GitHub. Usage: python scripts/01_download_data.py [dataset_name]"""
import _bootstrap  # noqa: F401
import sys

from traceguard import config as C
from traceguard import data as D

name = sys.argv[1] if len(sys.argv) > 1 else C.DATASET_NAME
folder = D.download_dataset(name)
print("Data ready in:", folder)
for f in sorted(folder.glob("*.csv")):
    print(" -", f.name)
