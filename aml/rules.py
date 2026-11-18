"""Rule based transaction monitoring.

Each rule contributes a weight to a transaction level risk score.  Transactions
at or above ``rules.alert_threshold`` become alerts and carry the plain English
reasons that fired.  Thresholds and weights come from
:class:`aml.config.RuleConfig` so tuning does not require editing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, AnalysisConfig
from .io import DataError, read_table, write_table

REQUIRED_MONITORING_COLUMNS = (
    "transaction_id",
    "customer_id",
    "bank_id",
    "transaction_datetime",
    "transaction_type",
    "amount",
    "counterparty_country",
    "country_risk_score",
    "pep_flag",
)

ALERT_COLUMNS = (
    "alert_id",
    "transaction_id",
    "customer_id",
    "bank_id",
    "transaction_datetime",
    "amount",
    "transaction_type",
    "counterparty_country",
    "risk_score",
    "risk_tier",
    "alert_reasons",
)

#: rule column, human readable reason, weight attribute on RuleConfig
RULE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("rule_high_value", "High-value transaction", "weight_high_value"),
    ("rule_structuring", "Near-threshold cash deposit", "weight_structuring"),
    ("rule_high_risk_country", "High-risk jurisdiction", "weight_high_risk_country"),
    ("rule_velocity", "Unusually high transaction velocity", "weight_velocity"),
    ("rule_pep", "PEP with elevated transaction", "weight_pep"),
)


@dataclass(frozen=True)
class MonitoringResult:
    """Scored transactions plus the subset that became alerts."""

    scored: pd.DataFrame
    alerts: pd.DataFrame


def _validate(transactions: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_MONITORING_COLUMNS if column not in transactions.columns]
    if missing:
        raise DataError("transactions are missing required column(s): " + ", ".join(missing))
    duplicated = transactions["transaction_id"].duplicated()
    if bool(duplicated.any()):
        examples = transactions.loc[duplicated, "transaction_id"].astype(str).head(3).tolist()
        raise DataError(
            f"duplicate transaction ids detected ({int(duplicated.sum())} row(s), "
            f"first: {', '.join(examples)})"
        )
    if transactions["amount"].isna().any():
        raise DataError("transaction amounts contain missing values")
    non_positive = transactions["amount"] < 0
    if bool(non_positive.any()):
        raise DataError(
            f"transaction amounts must not be negative ({int(non_positive.sum())} row(s))"
        )
    return transactions


def transaction_counts_in_window(
    ordered_times: np.ndarray,
    window: pd.Timedelta,
) -> np.ndarray:
    """Count transactions in ``[t - window, t]`` up to and including each row.

    ``ordered_times`` must be sorted ascending.  Rows that share a timestamp are
    counted once each as they appear, which keeps the original rule semantics:
    a transaction cannot be in the window of a transaction that has not been
    seen yet.
    """
    if ordered_times.size == 0:
        return np.empty(0, dtype=np.int64)
    delta = np.timedelta64(window.value, "ns")
    left = np.searchsorted(ordered_times, ordered_times - delta, side="left")
    positions = np.arange(ordered_times.size, dtype=np.int64)
    return positions - left + 1


def _velocity_counts(transactions: pd.DataFrame, window: pd.Timedelta) -> pd.Series:
    # Work on a positional index: the frame index may be arbitrary labels after
    # sorting, and using those labels as array positions silently misplaces
    # every count.
    positional = transactions.reset_index(drop=True)
    counts = np.zeros(len(positional), dtype=np.int64)
    for _, group in positional.groupby("customer_id", sort=False):
        counts[group.index.to_numpy()] = transaction_counts_in_window(
            group["transaction_datetime"].to_numpy(), window
        )
    return pd.Series(counts, index=transactions.index, name="tx_count_1h")


def apply_rules(
    transactions: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Score every transaction and attach rule flags, reasons and risk tiers."""
    transactions = _validate(transactions)
    rules = config.rules
    window = pd.Timedelta(rules.velocity_window)

    scored = transactions.sort_values(["customer_id", "transaction_datetime"]).copy()

    scored["rule_high_value"] = scored["amount"] >= rules.high_value_threshold
    scored["rule_structuring"] = (
        scored["transaction_type"].eq(rules.structuring_transaction_type)
        & scored["amount"].between(rules.structuring_min_amount, rules.structuring_max_amount)
    )
    scored["rule_high_risk_country"] = (
        scored["country_risk_score"] >= rules.high_country_risk_threshold
    )
    scored["tx_count_1h"] = _velocity_counts(scored, window)
    scored["rule_velocity"] = scored["tx_count_1h"] >= rules.velocity_transaction_count
    scored["rule_pep"] = (scored["pep_flag"] == 1) & (scored["amount"] >= rules.pep_amount_threshold)

    risk_score = pd.Series(0, index=scored.index, dtype="int64")
    for rule_column, _, weight_attribute in RULE_SPECS:
        weight = getattr(rules, weight_attribute)
        if weight:
            risk_score = risk_score + scored[rule_column].astype("int64") * weight
    scored["risk_score"] = risk_score
    scored["alert_flag"] = scored["risk_score"] >= rules.alert_threshold

    reasons_by_rule = {rule_column: reason for rule_column, reason, _ in RULE_SPECS}

    def describe(row: pd.Series) -> str:
        return "; ".join(
            reasons_by_rule[rule_column]
            for rule_column, _, _ in RULE_SPECS
            if bool(row[rule_column])
        )

    scored["alert_reasons"] = scored.apply(describe, axis=1)
    scored["risk_tier"] = pd.cut(
        scored["risk_score"],
        bins=list(config.tiers.boundaries),
        labels=list(config.tiers.labels),
    )
    return scored


def extract_alerts(scored: pd.DataFrame) -> pd.DataFrame:
    """Return the alert view written to ``reports`` and ``data/processed``."""
    alerts = scored[scored["alert_flag"]].copy()
    alerts["alert_id"] = [f"A{index:06d}" for index in range(1, len(alerts) + 1)]
    return alerts[list(ALERT_COLUMNS)]


def monitor(
    transactions: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> MonitoringResult:
    """Score transactions and pull out the alerts in one step."""
    scored = apply_rules(transactions, config)
    return MonitoringResult(scored=scored, alerts=extract_alerts(scored))


def monitor_files(root: str | Path, config: AnalysisConfig = DEFAULT_CONFIG) -> MonitoringResult:
    """Read cleaned transactions below *root* and write the alert outputs."""
    root = Path(root)
    processed = root / "data" / "processed"
    reports = root / "reports"
    transactions = read_table(
        processed / "transactions_clean.csv",
        parse_dates=["transaction_datetime"],
        required=REQUIRED_MONITORING_COLUMNS,
    )
    result = monitor(transactions, config)
    write_table(result.alerts, reports / "sample_alert_report.csv")
    write_table(result.alerts, processed / "suspicious_alerts.csv")
    return result
