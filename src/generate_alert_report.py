"""Creates a concise periodic alert summary from the generated alert file.

Thin wrapper kept so the command documented in the README still works:

    python src/generate_alert_report.py

The implementation lives in :mod:`aml.reporting`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aml.cli import main  # noqa: E402  (the path has to be set up first)

if __name__ == "__main__":
    raise SystemExit(main(["report", "--root", str(ROOT)]))
