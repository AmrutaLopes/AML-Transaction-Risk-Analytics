"""End to end pipeline behaviour and reproducibility."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from aml import AnalysisConfig, DataError, run_pipeline

CONFIG = AnalysisConfig()
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fingerprint(root: Path) -> dict[str, str]:
    digests = {}
    for path in sorted(root.rglob("*.csv")) + sorted(root.rglob("*.json")):
        digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_full_run_reproduces_the_published_numbers(data_root):
    summary = run_pipeline(data_root, CONFIG)
    assert summary.transactions_cleaned == 6182
    assert summary.alerts == 90
    assert summary.alert_tiers == {"Low": 0, "Medium": 35, "High": 55, "Critical": 0}
    assert summary.customers_scored == 300
    assert summary.customer_tiers == {"Low": 279, "Medium": 11, "High": 10, "Critical": 0}


def test_run_writes_every_documented_output(data_root):
    run_pipeline(data_root, CONFIG)
    expected = [
        "data/processed/customers_clean.csv",
        "data/processed/banks_clean.csv",
        "data/processed/locations_clean.csv",
        "data/processed/transactions_clean.csv",
        "data/processed/customer_risk_features.csv",
        "data/processed/transaction_features.csv",
        "data/processed/suspicious_alerts.csv",
        "data/processed/customer_risk.csv",
        "reports/sample_alert_report.csv",
        "reports/alert_summary.csv",
        "reports/rule_hits.csv",
        "reports/data_quality.json",
    ]
    for relative in expected:
        assert (data_root / relative).is_file(), relative


def test_second_run_produces_identical_bytes(data_root):
    run_pipeline(data_root, CONFIG)
    first = fingerprint(data_root)
    run_pipeline(data_root, CONFIG)
    assert fingerprint(data_root) == first


def test_alerts_match_the_committed_report(data_root):
    run_pipeline(data_root, CONFIG)
    produced = pd.read_csv(data_root / "reports" / "sample_alert_report.csv")
    published = pd.read_csv(PROJECT_ROOT / "reports" / "sample_alert_report.csv")
    pd.testing.assert_frame_equal(produced, published)


def test_cleaned_transactions_match_the_committed_dataset(data_root):
    run_pipeline(data_root, CONFIG)
    produced = pd.read_csv(data_root / "data" / "processed" / "transactions_clean.csv")
    published = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "transactions_clean.csv")
    pd.testing.assert_frame_equal(produced, published)


def test_summary_matches_the_committed_report(data_root):
    run_pipeline(data_root, CONFIG)
    produced = pd.read_csv(data_root / "reports" / "alert_summary.csv")
    published = pd.read_csv(PROJECT_ROOT / "reports" / "alert_summary.csv")
    pd.testing.assert_frame_equal(produced, published)


def test_configuration_changes_reach_the_alerts(data_root):
    from dataclasses import replace

    strict_rules = replace(CONFIG.rules, high_value_threshold=20_000.0)
    strict = replace(CONFIG, rules=strict_rules)
    lenient = run_pipeline(data_root, CONFIG)
    strict_summary = run_pipeline(data_root, strict)
    assert strict_summary.alert_tiers["High"] < lenient.alert_tiers["High"]


def test_report_only_step_skips_the_quality_file(data_root):
    run_pipeline(data_root, CONFIG)
    quality = data_root / "reports" / "data_quality.json"
    quality.unlink()
    summary = run_pipeline(data_root, CONFIG, ("report",))
    assert summary.alerts == 90
    assert not quality.exists()


def test_given_steps_are_executed_in_isolation(data_root):
    run_pipeline(data_root, CONFIG, ("clean", "features"))
    assert (data_root / "data" / "processed" / "customer_risk_features.csv").is_file()
    assert not (data_root / "reports" / "sample_alert_report.csv").exists()


def test_monitor_requires_the_cleaned_transactions(data_root):
    with pytest.raises(DataError):
        run_pipeline(data_root, CONFIG, ("monitor",))


def test_unknown_step_is_rejected(data_root):
    with pytest.raises(ValueError) as error:
        run_pipeline(data_root, CONFIG, ("clean", "publish"))
    assert "publish" in str(error.value)


def test_empty_step_list_is_rejected(data_root):
    with pytest.raises(ValueError) as error:
        run_pipeline(data_root, CONFIG, ())
    assert "at least one" in str(error.value)


def test_missing_root_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        run_pipeline(tmp_path / "nowhere", CONFIG)
    assert "not found" in str(error.value)
