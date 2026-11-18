"""Cleaning rules, row accounting and the CSV conventions."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pandas as pd
import pytest

from aml import DataError, clean_datasets, clean_frame, read_table, write_table
from aml.io import CSV_LINETERMINATOR
from tests.conftest import customer_frame, location_frame, raw_transaction_frame


def build(transactions, customers=None, locations=None):
    customers = customers if customers is not None else customer_frame([{"customer_id": "C1"}])
    locations = locations if locations is not None else location_frame([{"location_id": "L001"}])
    return clean_frame(transactions, customers, locations)


def test_rows_without_a_key_are_dropped_and_counted():
    frame = raw_transaction_frame(
        [
            {"transaction_id": "T1", "amount": 100},
            {"transaction_id": None, "amount": 50},
            {"transaction_id": "T3", "customer_id": None, "amount": 20},
            {"transaction_id": "T4", "amount": "not a number"},
        ]
    )
    cleaned, _, report = build(frame)
    assert len(cleaned) == 1
    assert report.dropped_missing_keys == 3
    assert report.dropped_total == 3


def test_non_positive_amounts_are_dropped_and_counted():
    frame = raw_transaction_frame(
        [
            {"transaction_id": "T1", "amount": 10},
            {"transaction_id": "T2", "amount": 0},
            {"transaction_id": "T3", "amount": -5},
        ]
    )
    cleaned, _, report = build(frame)
    assert list(cleaned["transaction_id"]) == ["T1"]
    assert report.dropped_non_positive_amount == 2


def test_duplicate_ids_keep_the_first_row():
    frame = raw_transaction_frame(
        [
            {"transaction_id": "T1", "amount": 10},
            {"transaction_id": "T1", "amount": 99},
        ]
    )
    cleaned, _, report = build(frame)
    assert len(cleaned) == 1
    assert cleaned.loc[0, "amount"] == 10
    assert report.dropped_duplicate_ids == 1


def test_enriched_columns_are_appended_in_published_order():
    frame = raw_transaction_frame([{"transaction_id": "T1"}])
    cleaned, _, _ = build(frame)
    assert list(cleaned.columns)[-4:] == [
        "country_risk_score",
        "home_country_code",
        "pep_flag",
        "kyc_status",
    ]


def test_customer_text_fields_are_trimmed_and_title_cased():
    customers = customer_frame(
        [{"customer_id": "C1", "customer_type": "  sme ", "kyc_status": " review required "}]
    )
    _, cleaned_customers, _ = build(raw_transaction_frame([{"transaction_id": "T1"}]), customers=customers)
    assert cleaned_customers.loc[0, "customer_type"] == "Sme"
    assert cleaned_customers.loc[0, "kyc_status"] == "Review Required"


def test_unknown_location_leaves_a_missing_risk_score_and_is_counted():
    frame = raw_transaction_frame([{"transaction_id": "T1", "location_id": "L999"}])
    cleaned, _, report = build(frame)
    assert report.unmatched_locations == 1
    assert pd.isna(cleaned.loc[0, "country_risk_score"])


def test_unknown_customer_leaves_a_missing_kyc_status_and_is_counted():
    frame = raw_transaction_frame([{"transaction_id": "T1", "customer_id": "C999"}])
    cleaned, _, report = build(frame)
    assert report.unmatched_customers == 1
    assert pd.isna(cleaned.loc[0, "kyc_status"])


def test_missing_required_transaction_column_is_named():
    frame = raw_transaction_frame([{"transaction_id": "T1"}]).drop(columns=["amount"])
    with pytest.raises(ValueError) as error:
        build(frame)
    assert "amount" in str(error.value)


def test_columns_colliding_after_normalisation_are_reported():
    frame = raw_transaction_frame([{"transaction_id": "T1"}])
    frame = frame.rename(columns={"amount": "Amount"})
    frame["amount"] = 1.0
    with pytest.raises(ValueError) as error:
        build(frame)
    assert "collide" in str(error.value)


def test_import_does_not_create_directories(tmp_path):
    """Importing the package must not touch the filesystem."""
    root = str(pathlib.Path(__file__).resolve().parents[1])
    script = (
        "import os, sys;"
        f"sys.path.insert(0, {root!r});"
        "import aml, aml.cleaning, aml.rules;"
        "print(sorted(os.listdir('.')))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "[]"


def test_cleaned_csv_uses_crlf_terminators(tmp_path):
    path = write_table(pd.DataFrame({"a": [1, 2]}), tmp_path / "out.csv")
    payload = path.read_bytes()
    assert payload.count(b"\r\n") == 3
    assert payload.count(b"\n") == 3


def test_read_table_names_the_missing_file(tmp_path):
    with pytest.raises(DataError) as error:
        read_table(tmp_path / "missing.csv")
    assert "missing.csv" in str(error.value)


def test_read_table_names_the_missing_column(tmp_path):
    path = write_table(pd.DataFrame({"transaction_id": ["T1"]}), tmp_path / "transactions.csv")
    with pytest.raises(DataError) as error:
        read_table(path, required=("customer_id",))
    assert "transactions.csv" in str(error.value)
    assert "customer_id" in str(error.value)


def test_cleaning_the_committed_datasets_reproduces_the_published_counts(data_root):
    result = clean_datasets(data_root)
    assert result.report.raw_transactions == 6182
    assert result.report.cleaned_transactions == 6182
    assert result.report.dropped_total == 0
    assert result.report.customers == 300
    assert result.report.banks == 12
    assert result.report.locations == 20
    assert result.report.unmatched_locations == 0
    assert result.report.unmatched_customers == 0


def test_crlf_terminator_constant_is_used_by_the_writer():
    assert CSV_LINETERMINATOR == "\r\n"
