"""Report generation: summaries, rule breakdown and the data quality record."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from aml import (
    AnalysisConfig,
    alert_summary,
    clean_datasets,
    data_quality_report,
    monitor,
    read_table,
    rule_hits,
)
from aml.reporting import write_report_files
from tests.conftest import transaction_frame

CONFIG = AnalysisConfig()


def sample_alerts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "alert_id": ["A000001", "A000002", "A000003"],
            "amount": [100.0, 200.0, 300.5],
            "risk_tier": ["Medium", "High", "High"],
        }
    )


def test_summary_is_ordered_from_the_most_severe_tier():
    summary = alert_summary(sample_alerts(), CONFIG)
    assert list(summary["risk_tier"]) == ["High", "Medium"]
    assert list(summary["alert_count"]) == [2, 1]


def test_summary_values_are_rounded():
    summary = alert_summary(sample_alerts(), CONFIG).set_index("risk_tier")
    assert summary.loc["High", "total_value"] == pytest.approx(500.5)
    assert summary.loc["High", "average_value"] == pytest.approx(250.25)


def test_rule_breakdown_counts_transactions_and_alerts(built_project):
    transactions = read_table(
        built_project / "data" / "processed" / "transactions_clean.csv",
        parse_dates=["transaction_datetime"],
    )
    hits = rule_hits(monitor(transactions, CONFIG).scored, CONFIG).set_index("rule")
    assert hits.loc["rule_high_value", "transactions"] == 85
    assert hits.loc["rule_high_value", "alerts"] == 39
    assert hits.loc["rule_structuring", "weight"] == 30
    assert set(hits.index) == {
        "rule_high_value",
        "rule_structuring",
        "rule_high_risk_country",
        "rule_velocity",
        "rule_pep",
    }


def test_rule_breakdown_follows_configured_weights():
    frame = transaction_frame([{"transaction_id": "T1", "amount": 20_000}])
    scored = monitor(frame, CONFIG).scored
    from dataclasses import replace

    tuned = replace(CONFIG, rules=replace(CONFIG.rules, weight_high_value=99))
    hits = rule_hits(scored, tuned).set_index("rule")
    assert hits.loc["rule_high_value", "weight"] == 99


def test_data_quality_report_records_counts_and_rates(built_project):
    result = clean_datasets(built_project)
    monitored = monitor(result.transactions, CONFIG)
    quality = data_quality_report(result.report, monitored.scored, monitored.alerts, CONFIG)
    assert quality["rows"]["cleaned_transactions"] == 6182
    assert quality["rows"]["dropped_total"] == 0
    assert quality["rows"]["banks"] == 12
    assert quality["monitoring"]["alerts"] == 90
    assert quality["monitoring"]["alert_rate"] == pytest.approx(90 / 6182, abs=1e-6)
    assert quality["monitoring"]["transactions_by_tier"]["High"] == 55


def test_report_files_use_crlf_and_skip_quality_without_a_cleaning_report(tmp_path):
    frame = transaction_frame(
        [{"transaction_id": "T1", "amount": 20_000, "country_risk_score": 5, "pep_flag": 1}]
    )
    result = monitor(frame, CONFIG)
    paths = write_report_files(tmp_path, result.scored, result.alerts, CONFIG)
    assert set(paths) == {"summary", "rule_hits"}
    for path in paths.values():
        payload = path.read_bytes()
        assert payload.count(b"\n") == payload.count(b"\r\n")
        assert payload.count(b"\r\n") >= 2


def test_quality_file_is_written_when_cleaning_ran(built_project, tmp_path):
    result = clean_datasets(built_project)
    monitored = monitor(result.transactions, CONFIG)
    paths = write_report_files(
        tmp_path, monitored.scored, monitored.alerts, CONFIG, cleaning=result.report
    )
    payload = paths["data_quality"].read_bytes()
    assert payload.count(b"\n") == payload.count(b"\r\n")
    document = json.loads(payload.decode("utf-8"))
    assert document["monitoring"]["alerts"] == 90
    assert document["referential_integrity"]["transactions_without_customer"] == 0
