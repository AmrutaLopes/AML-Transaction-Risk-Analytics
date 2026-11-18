"""Feature engineering: window counts, thresholds and alignment."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from aml import AnalysisConfig, DataError, build_features, counts_in_window, max_counts_in_window
from tests.conftest import transaction_frame

WINDOW = pd.Timedelta("24h")


def naive_max_count(times: pd.Series, window: pd.Timedelta) -> int:
    values = sorted(pd.Timestamp(value) for value in times)
    best = 0
    for moment in values:
        count = sum(1 for other in values if moment - window <= other <= moment)
        best = max(best, count)
    return best


def test_counts_in_window_matches_a_brute_force_reference():
    rng = np.random.default_rng(7)
    offsets = np.sort(rng.integers(0, 60 * 60 * 48, size=60))
    times = np.datetime64("2025-01-01T00:00:00") + offsets.astype("timedelta64[s]")
    counts = counts_in_window(times, WINDOW)
    expected = [
        int(((times >= moment - WINDOW.to_timedelta64()) & (times <= moment)).sum())
        for moment in times
    ]
    assert counts.tolist() == expected


def test_transactions_sharing_a_timestamp_are_counted_together():
    times = np.array(
        ["2025-01-01T10:00:00", "2025-01-01T10:00:00", "2025-01-01T10:00:00"],
        dtype="datetime64[s]",
    )
    assert counts_in_window(times, pd.Timedelta("1h")).tolist() == [3, 3, 3]


def test_window_boundary_is_inclusive_and_one_second_past_it_is_not():
    inside = np.array(["2025-01-01T00:00:00", "2025-01-02T00:00:00"], dtype="datetime64[s]")
    assert max_counts_in_window(inside, WINDOW) == 2
    outside = np.array(["2025-01-01T00:00:00", "2025-01-02T00:00:01"], dtype="datetime64[s]")
    assert max_counts_in_window(outside, WINDOW) == 1


def test_empty_series_yields_no_counts():
    assert counts_in_window(np.array([], dtype="datetime64[s]"), WINDOW).size == 0
    assert max_counts_in_window(np.array([], dtype="datetime64[s]"), WINDOW) == 0


def test_high_value_count_follows_the_configured_threshold():
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "customer_id": "C1", "amount": 15_000},
            {"transaction_id": "T2", "customer_id": "C1", "amount": 12_000},
            {"transaction_id": "T3", "customer_id": "C1", "amount": 9_000},
        ]
    )
    features, _ = build_features(frame, AnalysisConfig())
    assert features.loc[0, "high_value_tx_count"] == 2

    base = AnalysisConfig()
    stricter = replace(base, rules=replace(base.rules, high_value_threshold=13_000.0))
    features, _ = build_features(frame, stricter)
    assert features.loc[0, "high_value_tx_count"] == 1


def test_high_risk_country_count_follows_the_configured_threshold():
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "customer_id": "C1", "country_risk_score": 4},
            {"transaction_id": "T2", "customer_id": "C1", "country_risk_score": 5},
            {"transaction_id": "T3", "customer_id": "C1", "country_risk_score": 2},
        ]
    )
    features, _ = build_features(frame, AnalysisConfig())
    assert features.loc[0, "high_risk_country_tx_count"] == 2


def test_aggregates_are_attached_to_the_customer_that_earned_them():
    """Customers appear out of order; positional assignment would swap the counts."""
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "customer_id": "C2", "amount": 500, "transaction_datetime": "2025-01-01 23:00:00"},
            {"transaction_id": "T2", "customer_id": "C1", "amount": 100, "transaction_datetime": "2025-01-01 01:00:00"},
            {"transaction_id": "T3", "customer_id": "C1", "amount": 200, "transaction_datetime": "2025-01-01 02:00:00"},
            {"transaction_id": "T4", "customer_id": "C1", "amount": 300, "transaction_datetime": "2025-01-01 03:00:00"},
        ]
    )
    customer_features, _ = build_features(frame, AnalysisConfig())
    features = customer_features.set_index("customer_id")
    assert features.loc["C1", "transaction_count"] == 3
    assert features.loc["C2", "transaction_count"] == 1
    assert features.loc["C1", "total_transaction_value"] == pytest.approx(600.0)
    assert features.loc["C2", "velocity_24h"] == 1


def test_velocity_is_independent_of_the_input_index_labels():
    """A shuffled index must not move counts onto the wrong rows."""
    frame = transaction_frame(
        [
            {"transaction_id": f"T{i}", "customer_id": "C1", "transaction_datetime": f"2025-01-01 0{i}:00:00"}
            for i in range(1, 5)
        ]
    )
    shuffled = frame.iloc[[3, 0, 2, 1]].set_index(pd.Index([40, 10, 30, 20]))
    features_default, _ = build_features(frame, AnalysisConfig())
    features_shuffled, _ = build_features(shuffled, AnalysisConfig())
    assert features_default.loc[0, "velocity_24h"] == 4
    assert features_shuffled.loc[0, "velocity_24h"] == 4


def test_money_columns_are_rounded_to_two_decimals():
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "customer_id": "C1", "amount": 100.10},
            {"transaction_id": "T2", "customer_id": "C1", "amount": 200.20},
        ]
    )
    features, _ = build_features(frame, AnalysisConfig())
    assert features.loc[0, "total_transaction_value"] == pytest.approx(300.3)
    assert features.loc[0, "average_transaction_value"] == pytest.approx(150.15)


def test_transaction_features_gain_a_date_column():
    frame = transaction_frame([{"transaction_id": "T1"}])
    _, transaction_features = build_features(frame, AnalysisConfig())
    assert "date" in transaction_features.columns
    assert transaction_features.loc[0, "date"] == pd.Timestamp("2025-01-01").date()
    assert len(transaction_features) == len(frame)


def test_empty_input_produces_empty_frames_with_the_expected_columns():
    frame = transaction_frame([])
    customer_features, transaction_features = build_features(frame, AnalysisConfig())
    assert customer_features.empty
    assert list(customer_features.columns) == [
        "customer_id",
        "transaction_count",
        "total_transaction_value",
        "average_transaction_value",
        "max_transaction_value",
        "high_risk_country_tx_count",
        "average_country_risk",
        "high_value_tx_count",
        "velocity_24h",
    ]
    assert transaction_features.empty


def test_missing_required_column_is_named():
    frame = transaction_frame([{"transaction_id": "T1"}]).drop(columns=["country_risk_score"])
    with pytest.raises(DataError) as error:
        build_features(frame, AnalysisConfig())
    assert "country_risk_score" in str(error.value)


def test_velocity_uses_the_configured_window():
    frame = transaction_frame(
        [
            {"transaction_id": "T1", "customer_id": "C1", "transaction_datetime": "2025-01-01 00:00:00"},
            {"transaction_id": "T2", "customer_id": "C1", "transaction_datetime": "2025-01-01 05:00:00"},
        ]
    )
    wide, _ = build_features(frame, AnalysisConfig())
    assert wide.loc[0, "velocity_24h"] == 2

    narrow_config = AnalysisConfig(features=replace(AnalysisConfig().features, velocity_window="2h"))
    narrow, _ = build_features(frame, narrow_config)
    assert narrow.loc[0, "velocity_24h"] == 1
