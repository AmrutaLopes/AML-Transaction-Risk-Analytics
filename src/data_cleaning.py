"""Data preparation for the AML transaction-risk project.

Thin wrapper kept so the command documented in the README still works:

    python src/data_cleaning.py

The implementation lives in :mod:`aml.cleaning`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aml.cli import main  # noqa: E402  (the path has to be set up first)

if __name__ == "__main__":
    raise SystemExit(main(["clean", "--root", str(ROOT)]))
