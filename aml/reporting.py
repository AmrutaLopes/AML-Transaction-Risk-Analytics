"""Alert summaries, rule hit breakdowns and the data quality report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cleaning import CleaningReport
from .config import DEFAULT_CONFIG, AnalysisConfig
from .io import write_json, write_table
from .rules import RULE_SPECS

SUMMARY_COLUMNS = ("risk_tier", "alert_count", "total_value", "average_value")
RULE_HIT_COLUMNS = ("rule", "reason", "weight", "transactions", "alerts")


def alert_summary(
    alerts: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Alert counts and values per risk tier, most severe tier first."""
    summary = (
        alerts.assign(risk_tier=alerts["risk_tier"].astype(str))
        .groupby("risk_tier")
        .agg(
            alert_count=("alert_id", "count"),
            total_value=("amount", "sum"),
            average_value=("amount", "mean"),
        )
        .reset_index()
    )
    summary["total_value"] = summary["total_value"].round(2)
    summary["average_value"] = summary["average_value"].round(2)
    severity = [label for label in reversed(config.tiers.labels) if label in set(summary["risk_tier"])]
    summary = summary.set_index("risk_tier").reindex(severity).reset_index()
    return summary[list(SUMMARY_COLUMNS)]


def rule_hits(
    scored: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """How often each monitoring rule fired, and how many alerts it produced."""
    rows = []
    for rule_column, reason, weight_attribute in RULE_SPECS:
        triggered = scored[rule_column]
        rows.append(
            {
                "rule": rule_column,
                "reason": reason,
                "weight": getattr(config.rules, weight_attribute),
                "transactions": int(triggered.sum()),
                "alerts": int((triggered & scored["alert_flag"]).sum()),
            }
        )
    return pd.DataFrame(rows, columns=list(RULE_HIT_COLUMNS))


def data_quality_report(
    cleaning: CleaningReport,
    scored: pd.DataFrame,
    alerts: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> dict[str, object]:
    """A machine readable record of what the run kept, dropped and flagged."""
    transactions = len(scored)
    alert_count = len(alerts)
    tiers = scored["risk_tier"].value_counts().sort_index()
    tier_payload = {
        str(label): int(tiers.get(label, 0)) for label in config.tiers.labels
    }
    alert_tiers = alerts["risk_tier"].value_counts().sort_index()
    return {
        "rows": {
            "raw_transactions": cleaning.raw_transactions,
            "cleaned_transactions": cleaning.cleaned_transactions,
            "dropped_total": cleaning.dropped_total,
            "dropped_missing_keys": cleaning.dropped_missing_keys,
            "dropped_non_positive_amount": cleaning.dropped_non_positive_amount,
            "dropped_duplicate_ids": cleaning.dropped_duplicate_ids,
            "customers": cleaning.customers,
            "banks": cleaning.banks,
            "locations": cleaning.locations,
        },
        "referential_integrity": {
            "transactions_without_location": cleaning.unmatched_locations,
            "transactions_without_customer": cleaning.unmatched_customers,
        },
        "monitoring": {
            "transactions_scored": transactions,
            "alerts": alert_count,
            "alert_rate": round(alert_count / transactions, 6) if transactions else 0.0,
            "alert_threshold": config.rules.alert_threshold,
            "transactions_by_tier": tier_payload,
            "alerts_by_tier": {
                str(label): int(alert_tiers.get(label, 0)) for label in config.tiers.labels
            },
        },
    }


def write_report_files(
    root: str | Path,
    scored: pd.DataFrame,
    alerts: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
    cleaning: CleaningReport | None = None,
) -> dict[str, Path]:
    """Write the summary and rule breakdown, plus data quality when available."""
    reports = Path(root) / "reports"
    summary = alert_summary(alerts, config)
    hits = rule_hits(scored, config)

    paths = {
        "summary": write_table(summary, reports / "alert_summary.csv"),
        "rule_hits": write_table(hits, reports / "rule_hits.csv"),
    }

    if cleaning is not None:
        quality = data_quality_report(cleaning, scored, alerts, config)
        paths["data_quality"] = write_json(quality, reports / "data_quality.json")

    return paths
