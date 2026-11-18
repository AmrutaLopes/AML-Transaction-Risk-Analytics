"""Transaction monitoring rules, scoring and alert extraction."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from aml import AnalysisConfig, DataError, apply_rules, extract_alerts, monitor
from tests.conftest import transaction_frame


def scored(rows, config=None):
    return apply_rules(transaction_frame(rows), config or AnalysisConfig())


def alerts_of(rows, config=None):
    return extract_alerts(scored(rows, config))


def test_high_value_rule_fires_at_the_threshold():
    assert bool(scored([{"amount": 10_000}]).loc[0, "rule_high_value"]) is True
    assert bool(scored([{"amount": 9_999.99}]).loc[0, "rule_high_value"]) is False


def test_structuring_rule_covers_the_whole_band_for_cash_deposits():
    frame = scored(
        [
            {"transaction_id": "T1", "transaction_type": "Cash Deposit", "amount": 7_000},
            {"transaction_id": "T2", "transaction_type": "Cash Deposit", "amount": 9_999.99},
            {"transaction_id": "T3", "transaction_type": "Cash Deposit", "amount": 6_999.99},
            {"transaction_id": "T4", "transaction_type": "Card", "amount": 8_000},
        ]
    ).set_index("transaction_id")
    assert bool(frame.loc["T1", "rule_structuring"]) is True
    assert bool(frame.loc["T2", "rule_structuring"]) is True
    assert bool(frame.loc["T3", "rule_structuring"]) is False
    assert bool(frame.loc["T4", "rule_structuring"]) is False


def test_high_risk_country_rule_fires_at_the_threshold():
    assert bool(scored([{"country_risk_score": 4}]).loc[0, "rule_high_risk_country"]) is True
    assert bool(scored([{"country_risk_score": 3}]).loc[0, "rule_high_risk_country"]) is False


def test_missing_country_risk_does_not_trigger_the_rule():
    assert bool(scored([{"country_risk_score": None}]).loc[0, "rule_high_risk_country"]) is False


def test_velocity_rule_needs_the_configured_number_of_transactions():
    def burst(count: int):
        return [
            {"transaction_id": f"T{index}", "transaction_datetime": f"2025-01-01 09:{index:02d}:00"}
            for index in range(count)
        ]

    assert int(scored(burst(8))["rule_velocity"].sum()) == 1
    assert int(scored(burst(7))["rule_velocity"].sum()) == 0


def test_velocity_window_is_inclusive_at_exactly_one_hour():
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "transaction_datetime": "2025-01-01 08:00:00"},
            {"transaction_id": "T2", "transaction_datetime": "2025-01-01 09:00:00"},
        ]
    )
    result = apply_rules(frame, AnalysisConfig())
    assert result.loc[result["transaction_id"] == "T2", "tx_count_1h"].iloc[0] == 2

    frame.loc[1, "transaction_datetime"] = pd.Timestamp("2025-01-01 09:00:01")
    result = apply_rules(frame, AnalysisConfig())
    assert result.loc[result["transaction_id"] == "T2", "tx_count_1h"].iloc[0] == 1


def test_velocity_counts_only_rows_already_seen_for_identical_timestamps():
    """Two transactions at the same instant count 1 then 2, as the rule always did."""
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "transaction_datetime": "2025-01-01 09:00:00"},
            {"transaction_id": "T2", "transaction_datetime": "2025-01-01 09:00:00"},
        ]
    )
    result = apply_rules(frame, AnalysisConfig()).set_index("transaction_id")
    assert result.loc["T1", "tx_count_1h"] == 1
    assert result.loc["T2", "tx_count_1h"] == 2


def test_velocity_does_not_depend_on_the_input_index_labels():
    frame = transaction_frame(
        [
            {"transaction_id": f"T{index}", "transaction_datetime": f"2025-01-01 09:0{index}:00"}
            for index in range(4)
        ]
    )
    shuffled = frame.iloc[[2, 0, 3, 1]].set_index(pd.Index([900, 100, 700, 300]))
    plain = apply_rules(frame, AnalysisConfig()).set_index("transaction_id")
    mixed = apply_rules(shuffled, AnalysisConfig()).set_index("transaction_id")
    assert plain["tx_count_1h"].to_dict() == mixed["tx_count_1h"].to_dict()


def test_pep_rule_needs_both_the_flag_and_the_amount():
    frame = scored(
        [
            {"transaction_id": "T1", "pep_flag": 1, "amount": 5_000},
            {"transaction_id": "T2", "pep_flag": 1, "amount": 4_999},
            {"transaction_id": "T3", "pep_flag": 0, "amount": 20_000},
        ]
    ).set_index("transaction_id")
    assert bool(frame.loc["T1", "rule_pep"]) is True
    assert bool(frame.loc["T2", "rule_pep"]) is False
    assert bool(frame.loc["T3", "rule_pep"]) is False


def test_risk_score_adds_the_configured_weights():
    result = scored([{"amount": 20_000, "country_risk_score": 5}])
    assert result.loc[0, "risk_score"] == 45


def test_alert_threshold_is_inclusive():
    assert bool(scored([{"transaction_type": "Cash Deposit", "amount": 8_000}]).loc[0, "alert_flag"]) is True
    assert bool(scored([{"amount": 20_000}]).loc[0, "alert_flag"]) is False


def test_weights_are_read_from_the_configuration():
    config = AnalysisConfig()
    heavier = replace(config, rules=replace(config.rules, weight_high_value=50, alert_threshold=50))
    assert bool(scored([{"amount": 20_000}], heavier).loc[0, "alert_flag"]) is True


def test_reasons_are_listed_in_rule_order():
    result = scored([{"amount": 20_000, "country_risk_score": 5, "pep_flag": 1}])
    assert result.loc[0, "alert_reasons"] == (
        "High-value transaction; High-risk jurisdiction; PEP with elevated transaction"
    )


def test_transactions_without_a_hit_have_an_empty_reason():
    assert scored([{"amount": 100}]).loc[0, "alert_reasons"] == ""


def test_alert_ids_are_sequential_and_zero_padded():
    rows = [
        {
            "transaction_id": f"T{index}",
            "amount": 20_000,
            "country_risk_score": 5,
            "customer_id": f"C{index:03d}",
        }
        for index in range(3)
    ]
    alerts = alerts_of(rows)
    assert list(alerts["alert_id"]) == ["A000001", "A000002", "A000003"]


def test_risk_tiers_follow_the_configured_bands():
    result = scored(
        [
            {"transaction_id": "low", "amount": 100},
            {"transaction_id": "medium", "transaction_type": "Cash Deposit", "amount": 8_000},
            {"transaction_id": "high", "amount": 20_000, "country_risk_score": 5},
        ]
    ).set_index("transaction_id")
    assert result.loc["low", "risk_tier"] == "Low"
    assert result.loc["medium", "risk_tier"] == "Medium"
    assert result.loc["high", "risk_tier"] == "High"


def test_custom_tier_labels_are_used():
    config = AnalysisConfig()
    custom = replace(config, tiers=replace(config.tiers, labels=("Bajo", "Medio", "Alto", "Crítico")))
    result = scored([{"amount": 100}], custom)
    assert result.loc[0, "risk_tier"] == "Bajo"


def test_alert_view_has_the_published_columns():
    alerts = alerts_of([{"amount": 20_000}])
    assert list(alerts.columns) == [
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
    ]


def test_duplicate_transaction_ids_are_rejected_with_a_count():
    frame = transaction_frame([{"transaction_id": "T1"}, {"transaction_id": "T1"}])
    with pytest.raises(DataError) as error:
        apply_rules(frame, AnalysisConfig())
    assert "duplicate transaction ids" in str(error.value)
    assert "1 row" in str(error.value)


def test_negative_amounts_are_rejected():
    frame = transaction_frame([{"transaction_id": "T1", "amount": -1}])
    with pytest.raises(DataError) as error:
        apply_rules(frame, AnalysisConfig())
    assert "negative" in str(error.value)


def test_missing_monitoring_column_is_named():
    frame = transaction_frame([{"transaction_id": "T1"}]).drop(columns=["pep_flag"])
    with pytest.raises(DataError) as error:
        apply_rules(frame, AnalysisConfig())
    assert "pep_flag" in str(error.value)


def test_monitor_returns_scored_transactions_and_alerts():
    frame = transaction_frame([{"transaction_id": "T1", "amount": 20_000, "country_risk_score": 5}])
    result = monitor(frame, AnalysisConfig())
    assert len(result.scored) == 1
    assert len(result.alerts) == 1
    assert int(result.scored["alert_flag"].sum()) == 1
