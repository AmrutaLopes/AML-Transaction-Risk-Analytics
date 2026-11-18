"""Shared fixtures and small builders for the test suite."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAW_FILES = ("customers.csv", "transactions.csv", "banks.csv", "locations.csv")


RAW_TRANSACTION_DEFAULTS = {
    "transaction_id": "T1",
    "customer_id": "C1",
    "bank_id": "B1",
    "transaction_datetime": "2025-01-01 09:00:00",
    "transaction_type": "Card",
    "channel": "Mobile",
    "amount": 100.0,
    "currency": "GBP",
    "location_id": "L001",
    "counterparty_country": "GB",
    "beneficiary_type": "Individual",
    "description": "Payment",
}

ENRICHED_TRANSACTION_DEFAULTS = {
    **RAW_TRANSACTION_DEFAULTS,
    "country_risk_score": 1,
    "home_country_code": "GB",
    "pep_flag": 0,
    "kyc_status": "Verified",
}


def _frame(rows: list[dict], defaults: dict) -> pd.DataFrame:
    records = [{**defaults, **row} for row in rows]
    columns = list(dict.fromkeys(key for record in records for key in record)) or list(defaults)
    frame = pd.DataFrame(records, columns=columns)
    frame["transaction_datetime"] = pd.to_datetime(frame["transaction_datetime"])
    return frame


def raw_transaction_frame(rows: list[dict]) -> pd.DataFrame:
    """Build a frame with exactly the columns the raw transactions file has."""
    return _frame(rows, RAW_TRANSACTION_DEFAULTS)


def transaction_frame(rows: list[dict]) -> pd.DataFrame:
    """Build an enriched transaction frame with the columns the rules require."""
    return _frame(rows, ENRICHED_TRANSACTION_DEFAULTS)


def customer_frame(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "customer_id": "C1",
        "customer_name": "Test Customer",
        "customer_type": "Retail",
        "age": 40,
        "home_country": "United Kingdom",
        "home_country_code": "GB",
        "annual_income": 50000.0,
        "account_open_date": pd.Timestamp("2020-01-01"),
        "pep_flag": 0,
        "kyc_status": "Verified",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def location_frame(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "location_id": "L001",
        "country": "United Kingdom",
        "country_code": "GB",
        "country_risk_score": 1,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


@pytest.fixture()
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    """A throwaway project root holding only the committed raw datasets."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    for name in RAW_FILES:
        shutil.copy2(PROJECT_ROOT / "data" / "raw" / name, raw / name)
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture(scope="session")
def built_project(tmp_path_factory) -> Path:
    """A project root with the whole pipeline already applied once."""
    from aml import run_pipeline

    root = tmp_path_factory.mktemp("built")
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    for name in RAW_FILES:
        shutil.copy2(PROJECT_ROOT / "data" / "raw" / name, raw / name)
    run_pipeline(root)
    return root
