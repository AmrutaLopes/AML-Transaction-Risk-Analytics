"""Data preparation for the AML transaction risk pipeline.

The module is import safe: it touches the filesystem only when one of its
functions is called, so importing it (or the package) never creates
directories as a side effect.

Every dropped row is counted and reported through :class:`CleaningReport`
instead of disappearing silently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_table

CUSTOMER_COLUMNS = (
    "customer_id",
    "customer_name",
    "customer_type",
    "age",
    "home_country",
    "home_country_code",
    "annual_income",
    "account_open_date",
    "pep_flag",
    "kyc_status",
)

TRANSACTION_COLUMNS = (
    "transaction_id",
    "customer_id",
    "bank_id",
    "transaction_datetime",
    "transaction_type",
    "channel",
    "amount",
    "currency",
    "location_id",
    "counterparty_country",
    "beneficiary_type",
    "description",
)

BANK_COLUMNS = ("bank_id", "bank_name", "country_code")
LOCATION_COLUMNS = ("location_id", "country", "country_code", "country_risk_score")


@dataclass(frozen=True)
class CleaningReport:
    """Row counts collected while preparing the datasets."""

    raw_transactions: int
    dropped_missing_keys: int
    dropped_non_positive_amount: int
    dropped_duplicate_ids: int
    cleaned_transactions: int
    unmatched_locations: int
    unmatched_customers: int
    customers: int
    banks: int
    locations: int

    @property
    def dropped_total(self) -> int:
        return self.raw_transactions - self.cleaned_transactions

    def to_dict(self) -> dict[str, int]:
        payload: dict[str, Any] = asdict(self)
        payload["dropped_total"] = self.dropped_total
        return payload


@dataclass(frozen=True)
class CleaningResult:
    """Cleaned frames plus the row accounting for the run."""

    customers: pd.DataFrame
    transactions: pd.DataFrame
    banks: pd.DataFrame
    locations: pd.DataFrame
    report: CleaningReport


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Lower-case and trim column names, refusing ambiguous renames."""
    renamed = frame.rename(columns=lambda name: str(name).strip().lower())
    duplicated = renamed.columns[renamed.columns.duplicated()].tolist()
    if duplicated:
        raise ValueError(
            "column names collide after normalisation: " + ", ".join(sorted(set(duplicated)))
        )
    return renamed


def clean_frame(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    locations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, CleaningReport]:
    """Clean the transaction and customer frames and account for every dropped row."""
    transactions = _normalise_columns(transactions)
    customers = _normalise_columns(customers)
    locations = _normalise_columns(locations)

    missing = [column for column in TRANSACTION_COLUMNS if column not in transactions.columns]
    if missing:
        raise ValueError("transactions are missing required column(s): " + ", ".join(missing))
    missing = [column for column in CUSTOMER_COLUMNS if column not in customers.columns]
    if missing:
        raise ValueError("customers are missing required column(s): " + ", ".join(missing))
    missing = [column for column in LOCATION_COLUMNS if column not in locations.columns]
    if missing:
        raise ValueError("locations are missing required column(s): " + ", ".join(missing))

    raw_transactions = len(transactions)

    transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce")
    typed = transactions.dropna(subset=["transaction_id", "customer_id", "amount"])
    dropped_missing_keys = raw_transactions - len(typed)

    positive = typed[typed["amount"] > 0]
    dropped_non_positive_amount = len(typed) - len(positive)

    deduplicated = positive.drop_duplicates("transaction_id")
    dropped_duplicate_ids = len(positive) - len(deduplicated)

    customers["customer_type"] = customers["customer_type"].str.strip().str.title()
    customers["kyc_status"] = customers["kyc_status"].str.strip().str.title()

    unmatched_locations = int((~deduplicated["location_id"].isin(locations["location_id"])).sum())
    unmatched_customers = int((~deduplicated["customer_id"].isin(customers["customer_id"])).sum())

    enriched = deduplicated.merge(
        locations[["location_id", "country_risk_score"]],
        on="location_id",
        how="left",
    )
    enriched = enriched.merge(
        customers[["customer_id", "home_country_code", "pep_flag", "kyc_status"]],
        on="customer_id",
        how="left",
    )

    report = CleaningReport(
        raw_transactions=raw_transactions,
        dropped_missing_keys=dropped_missing_keys,
        dropped_non_positive_amount=dropped_non_positive_amount,
        dropped_duplicate_ids=dropped_duplicate_ids,
        cleaned_transactions=len(enriched),
        unmatched_locations=unmatched_locations,
        unmatched_customers=unmatched_customers,
        customers=len(customers),
        banks=0,
        locations=len(locations),
    )
    return enriched, customers, report


def clean_datasets(root: str | Path) -> CleaningResult:
    """Clean the synthetic datasets below ``root/data``."""
    root = Path(root)
    raw = root / "data" / "raw"

    transactions = read_table(
        raw / "transactions.csv",
        parse_dates=["transaction_datetime"],
        required=TRANSACTION_COLUMNS,
    )
    customers = read_table(
        raw / "customers.csv",
        parse_dates=["account_open_date"],
        required=CUSTOMER_COLUMNS,
    )
    banks = read_table(raw / "banks.csv", required=BANK_COLUMNS)
    locations = read_table(raw / "locations.csv", required=LOCATION_COLUMNS)

    cleaned, customers, report = clean_frame(transactions, customers, locations)
    report = replace(report, banks=len(banks))
    return CleaningResult(
        customers=customers,
        transactions=cleaned,
        banks=banks,
        locations=locations,
        report=report,
    )
