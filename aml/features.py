"""Customer and transaction feature engineering.

The previous implementation assigned per-customer aggregates back to the frame
with ``.values``, which only lined up while both groupbys happened to sort in
the same order.  Aggregates are now merged on ``customer_id``.  The rolling
window count is computed with a binary search instead of comparing every
transaction against every other transaction of the same customer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, AnalysisConfig
from .io import DataError, read_table, write_table

REQUIRED_FEATURE_COLUMNS = (
    "transaction_id",
    "customer_id",
    "transaction_datetime",
    "amount",
    "country_risk_score",
)

CUSTOMER_FEATURE_COLUMNS = (
    "customer_id",
    "transaction_count",
    "total_transaction_value",
    "average_transaction_value",
    "max_transaction_value",
    "high_risk_country_tx_count",
    "average_country_risk",
    "high_value_tx_count",
    "velocity_24h",
)


def counts_in_window(times: np.ndarray, window: pd.Timedelta) -> np.ndarray:
    """Count transactions inside ``[t - window, t]`` for every timestamp *t*.

    ``times`` must be sorted ascending.  Ties (several transactions with the
    same timestamp) are counted at once, which is what "transactions in the
    last N hours" means to an investigator.
    """
    if times.size == 0:
        return np.empty(0, dtype=np.int64)
    delta = np.timedelta64(window.value, "ns")
    left = np.searchsorted(times, times - delta, side="left")
    right = np.searchsorted(times, times, side="right")
    return (right - left).astype(np.int64)


def max_counts_in_window(times: np.ndarray, window: pd.Timedelta) -> int:
    """Highest number of transactions seen inside any window of the series."""
    counts = counts_in_window(times, window)
    if counts.size == 0:
        return 0
    return int(counts.max())


def _velocity_by_customer(
    transactions: pd.DataFrame,
    window: pd.Timedelta,
    customer_column: str = "customer_id",
    time_column: str = "transaction_datetime",
) -> pd.Series:
    ordered = transactions.sort_values([customer_column, time_column])
    values = ordered.groupby(customer_column, sort=True)[time_column].apply(
        lambda series: max_counts_in_window(series.to_numpy(), window)
    )
    values.name = "velocity_24h"
    return values


def build_features(
    transactions: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(customer_features, transaction_features)``."""
    missing = [column for column in REQUIRED_FEATURE_COLUMNS if column not in transactions.columns]
    if missing:
        raise DataError(
            "cleaned transactions are missing required column(s): " + ", ".join(missing)
        )

    features = transactions.copy()
    if not pd.api.types.is_datetime64_any_dtype(features["transaction_datetime"]):
        features["transaction_datetime"] = pd.to_datetime(features["transaction_datetime"])
    features["date"] = features["transaction_datetime"].dt.date

    high_risk_threshold = config.rules.high_country_risk_threshold
    high_value_threshold = config.rules.high_value_threshold
    window = pd.Timedelta(config.features.velocity_window)

    if features.empty:
        empty_customers = pd.DataFrame(
            {
                "customer_id": pd.Series(dtype=object),
                "transaction_count": pd.Series(dtype="int64"),
                "total_transaction_value": pd.Series(dtype="float64"),
                "average_transaction_value": pd.Series(dtype="float64"),
                "max_transaction_value": pd.Series(dtype="float64"),
                "high_risk_country_tx_count": pd.Series(dtype="int64"),
                "average_country_risk": pd.Series(dtype="float64"),
                "high_value_tx_count": pd.Series(dtype="int64"),
                "velocity_24h": pd.Series(dtype="int64"),
            }
        )
        return empty_customers, features

    customer_features = (
        features.groupby("customer_id")
        .agg(
            transaction_count=("transaction_id", "count"),
            total_transaction_value=("amount", "sum"),
            average_transaction_value=("amount", "mean"),
            max_transaction_value=("amount", "max"),
            high_risk_country_tx_count=(
                "country_risk_score",
                lambda values: int((values >= high_risk_threshold).sum()),
            ),
            average_country_risk=("country_risk_score", "mean"),
        )
        .reset_index()
    )

    high_value_counts = (
        features.assign(_high_value=features["amount"] >= high_value_threshold)
        .groupby("customer_id")["_high_value"]
        .sum()
        .astype("int64")
        .rename("high_value_tx_count")
        .reset_index()
    )
    velocity = _velocity_by_customer(features, window).reset_index()

    customer_features = customer_features.merge(high_value_counts, on="customer_id", how="left")
    customer_features = customer_features.merge(velocity, on="customer_id", how="left")
    customer_features["high_value_tx_count"] = (
        customer_features["high_value_tx_count"].fillna(0).astype("int64")
    )
    customer_features["velocity_24h"] = (
        customer_features["velocity_24h"].fillna(0).astype("int64")
    )
    customer_features["average_transaction_value"] = customer_features[
        "average_transaction_value"
    ].round(2)
    customer_features["average_country_risk"] = customer_features["average_country_risk"].round(2)
    # Totals are currency amounts: rounding removes binary float dust
    # (29795.010000000002) that otherwise changes the written file between
    # pandas versions and platforms.
    customer_features["total_transaction_value"] = customer_features[
        "total_transaction_value"
    ].round(2)
    customer_features = customer_features[list(CUSTOMER_FEATURE_COLUMNS)]
    return customer_features, features


def build_feature_files(root: str | Path, config: AnalysisConfig = DEFAULT_CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the cleaned transactions below *root* and rebuild the feature tables."""
    root = Path(root)
    processed = root / "data" / "processed"
    transactions = read_table(
        processed / "transactions_clean.csv",
        parse_dates=["transaction_datetime"],
        required=REQUIRED_FEATURE_COLUMNS,
    )
    customer_features, transaction_features = build_features(transactions, config)
    write_table(customer_features, processed / "customer_risk_features.csv")
    write_table(transaction_features, processed / "transaction_features.csv")
    return customer_features, transaction_features
