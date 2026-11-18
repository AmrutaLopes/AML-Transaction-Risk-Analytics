"""End to end orchestration of the cleaning, feature, monitoring and scoring steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .cleaning import CleaningReport, clean_datasets
from .config import DEFAULT_CONFIG, AnalysisConfig
from .features import build_features
from .io import read_table, write_table
from .reporting import write_report_files
from .rules import REQUIRED_MONITORING_COLUMNS, apply_rules, extract_alerts, monitor
from .scoring import score_customers

STEPS: tuple[str, ...] = ("clean", "features", "monitor", "score", "report")


@dataclass(frozen=True)
class RunSummary:
    """What the pipeline produced, in the numbers an analyst cares about."""

    transactions_cleaned: int = 0
    alerts: int = 0
    alert_tiers: dict[str, int] = field(default_factory=dict)
    customers_scored: int = 0
    customer_tiers: dict[str, int] = field(default_factory=dict)
    steps: tuple[str, ...] = STEPS

    def to_dict(self) -> dict[str, object]:
        return {
            "transactions_cleaned": self.transactions_cleaned,
            "alerts": self.alerts,
            "alert_tiers": dict(self.alert_tiers),
            "customers_scored": self.customers_scored,
            "customer_tiers": dict(self.customer_tiers),
            "steps": list(self.steps),
        }


def _tier_counts(series: pd.Series, labels) -> dict[str, int]:
    counts = series.value_counts().sort_index()
    return {str(label): int(counts.get(label, 0)) for label in labels}


def _read_transactions(root: Path) -> pd.DataFrame:
    return read_table(
        root / "data" / "processed" / "transactions_clean.csv",
        parse_dates=["transaction_datetime"],
        required=REQUIRED_MONITORING_COLUMNS,
    )


def run_pipeline(
    root: str | Path,
    config: AnalysisConfig = DEFAULT_CONFIG,
    steps: tuple[str, ...] = STEPS,
) -> RunSummary:
    """Run the requested pipeline steps below *root*.

    Steps are additive: ``("monitor",)`` expects the cleaned transaction file to
    exist already, while the default runs the whole chain.  The data quality
    report is written only when the ``clean`` step runs in the same invocation,
    because it describes the rows that step dropped.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    unknown = [step for step in steps if step not in STEPS]
    if unknown:
        raise ValueError(
            f"unknown pipeline step(s): {', '.join(unknown)}; known steps are {', '.join(STEPS)}"
        )
    if not steps:
        raise ValueError("at least one pipeline step is required")

    processed = root / "data" / "processed"
    cleaning: CleaningReport | None = None
    scored: pd.DataFrame | None = None
    alerts: pd.DataFrame | None = None
    customer_scores: pd.DataFrame | None = None

    if "clean" in steps:
        cleaned = clean_datasets(root)
        write_table(cleaned.customers, processed / "customers_clean.csv")
        write_table(cleaned.banks, processed / "banks_clean.csv")
        write_table(cleaned.locations, processed / "locations_clean.csv")
        write_table(cleaned.transactions, processed / "transactions_clean.csv")
        cleaning = cleaned.report

    if "features" in steps:
        customer_features, transaction_features = build_features(_read_transactions(root), config)
        write_table(customer_features, processed / "customer_risk_features.csv")
        write_table(transaction_features, processed / "transaction_features.csv")

    if "monitor" in steps:
        result = monitor(_read_transactions(root), config)
        scored = result.scored
        alerts = result.alerts
        write_table(alerts, root / "reports" / "sample_alert_report.csv")
        write_table(alerts, processed / "suspicious_alerts.csv")

    if "score" in steps:
        features = read_table(processed / "customer_risk_features.csv")
        customers = read_table(processed / "customers_clean.csv")
        customer_scores = score_customers(features, customers, config)
        write_table(customer_scores, processed / "customer_risk.csv")

    if "report" in steps:
        if scored is None:
            scored = apply_rules(_read_transactions(root), config)
        if alerts is None:
            alerts = extract_alerts(scored)
        write_report_files(root, scored, alerts, config, cleaning=cleaning)

    return RunSummary(
        transactions_cleaned=int(len(scored)) if scored is not None else 0,
        alerts=int(len(alerts)) if alerts is not None else 0,
        alert_tiers=_tier_counts(alerts["risk_tier"], config.tiers.labels) if alerts is not None else {},
        customers_scored=int(len(customer_scores)) if customer_scores is not None else 0,
        customer_tiers=(
            _tier_counts(customer_scores["customer_risk_tier"], config.tiers.labels)
            if customer_scores is not None
            else {}
        ),
        steps=tuple(steps),
    )
