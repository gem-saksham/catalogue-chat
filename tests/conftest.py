import sys
from pathlib import Path

# Ensure `app` package is importable when running tests from repo root
ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
