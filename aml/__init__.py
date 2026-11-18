"""AML transaction risk analytics.

A small, configurable pipeline over the synthetic dataset shipped with this
repository: clean the raw tables, engineer customer and transaction features,
apply rule based transaction monitoring and score customers.

Typical use::

    from aml import AnalysisConfig, run_pipeline

    summary = run_pipeline(".", AnalysisConfig())
    print(summary.alerts)

The command line entry point is :func:`aml.cli.main` (``aml-risk`` when the
package is installed).
"""

from __future__ import annotations

__version__ = "1.0.0"

from .cleaning import CleaningReport, CleaningResult, clean_datasets, clean_frame
from .config import (
    DEFAULT_CONFIG,
    AnalysisConfig,
    ConfigError,
    CustomerScoringConfig,
    FeatureConfig,
    RuleConfig,
    TierConfig,
    config_from_mapping,
    load_config,
)
from .features import build_features, counts_in_window, max_counts_in_window
from .io import CSV_LINETERMINATOR, DataError, read_table, write_table
from .pipeline import STEPS, RunSummary, run_pipeline
from .reporting import alert_summary, data_quality_report, rule_hits
from .rules import RULE_SPECS, MonitoringResult, apply_rules, extract_alerts, monitor
from .scoring import score_customers, top_risky_customers

__all__ = [
    "AnalysisConfig",
    "CSV_LINETERMINATOR",
    "CleaningReport",
    "CleaningResult",
    "ConfigError",
    "CustomerScoringConfig",
    "DEFAULT_CONFIG",
    "DataError",
    "FeatureConfig",
    "MonitoringResult",
    "RULE_SPECS",
    "RuleConfig",
    "RunSummary",
    "STEPS",
    "TierConfig",
    "__version__",
    "alert_summary",
    "apply_rules",
    "build_features",
    "clean_datasets",
    "clean_frame",
    "config_from_mapping",
    "counts_in_window",
    "data_quality_report",
    "extract_alerts",
    "load_config",
    "max_counts_in_window",
    "monitor",
    "read_table",
    "rule_hits",
    "run_pipeline",
    "score_customers",
    "top_risky_customers",
    "write_table",
]
