import os, sys, tempfile
from pathlib import Path

# isolate test data from the real data directory before the app is imported
os.environ["LR_DATA_DIR"] = tempfile.mkdtemp(prefix="lr_test_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
