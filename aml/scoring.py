"""Customer level risk scoring.

The score is additive: each indicator the customer triggers adds the configured
points.  Tier cut-offs are shared with the transaction alerts through
:class:`aml.config.TierConfig`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DEFAULT_CONFIG, AnalysisConfig
from .io import DataError, read_table, write_table

REQUIRED_FEATURE_COLUMNS = (
    "customer_id",
    "total_transaction_value",
    "average_country_risk",
    "high_value_tx_count",
    "velocity_24h",
)


def score_customers(
    features: pd.DataFrame,
    customers: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Return ``features`` enriched with customer risk scores and tiers."""
    missing = [column for column in REQUIRED_FEATURE_COLUMNS if column not in features.columns]
    if missing:
        raise DataError(
            "customer risk features are missing required column(s): " + ", ".join(missing)
        )
    missing = [
        column
        for column in ("customer_id", "pep_flag", "kyc_status", "customer_type")
        if column not in customers.columns
    ]
    if missing:
        raise DataError("cleaned customers are missing required column(s): " + ", ".join(missing))

    scoring = config.customer_scoring
    scored = features.merge(
        customers[["customer_id", "pep_flag", "kyc_status", "customer_type"]],
        on="customer_id",
        how="left",
    )

    points = scoring.points_per_indicator
    score = (
        (scored["total_transaction_value"] >= scoring.total_value_threshold).astype("int64") * points
        + (scored["average_country_risk"] >= scoring.average_country_risk_threshold).astype("int64") * points
        + (scored["high_value_tx_count"] >= scoring.high_value_count_threshold).astype("int64") * points
        + (scored["velocity_24h"] >= scoring.velocity_24h_threshold).astype("int64") * points
        + (scored["pep_flag"] == 1).astype("int64") * scoring.pep_points
        + (scored["kyc_status"] == scoring.kyc_review_status).astype("int64") * scoring.kyc_review_points
    )
    scored["customer_risk_score"] = score
    scored["customer_risk_tier"] = pd.cut(
        scored["customer_risk_score"],
        bins=list(config.tiers.boundaries),
        labels=list(config.tiers.labels),
    )
    return scored


def top_risky_customers(scored: pd.DataFrame, limit: int) -> pd.DataFrame:
    """Return the highest scoring customers, best first.

    ``limit`` is validated here rather than by the caller: a zero limit used to
    be read as "no limit" and a negative one sliced from the wrong end.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError(f"limit must be an integer, got {limit!r}")
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    columns = [
        "customer_id",
        "customer_risk_score",
        "customer_risk_tier",
        "total_transaction_value",
        "high_value_tx_count",
        "velocity_24h",
    ]
    present = [column for column in columns if column in scored.columns]
    ordered = scored.sort_values(
        ["customer_risk_score", "total_transaction_value"], ascending=[False, False]
    )
    return ordered[present].head(limit)


def score_files(root: str | Path, config: AnalysisConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """Read the feature tables below *root* and write ``customer_risk.csv``."""
    root = Path(root)
    processed = root / "data" / "processed"
    features = read_table(
        processed / "customer_risk_features.csv", required=REQUIRED_FEATURE_COLUMNS
    )
    customers = read_table(processed / "customers_clean.csv")
    scored = score_customers(features, customers, config)
    write_table(scored, processed / "customer_risk.csv")
    return scored
