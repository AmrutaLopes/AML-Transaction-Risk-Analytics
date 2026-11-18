"""Customer risk scoring and the top-N report."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from aml import AnalysisConfig, DataError, score_customers, top_risky_customers
from tests.conftest import customer_frame


def features(**overrides):
    row = {
        "customer_id": "C1",
        "transaction_count": 5,
        "total_transaction_value": 1_000.0,
        "average_transaction_value": 200.0,
        "max_transaction_value": 400.0,
        "high_risk_country_tx_count": 0,
        "average_country_risk": 1.0,
        "high_value_tx_count": 0,
        "velocity_24h": 1,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def score(frame, customers=None, config=None):
    customers = customers if customers is not None else customer_frame([{"customer_id": "C1"}])
    return score_customers(frame, customers, config or AnalysisConfig())


def test_total_value_indicator_adds_the_configured_points():
    result = score(features(total_transaction_value=100_000.0))
    assert result.loc[0, "customer_risk_score"] == 20


def test_average_country_risk_indicator():
    assert score(features(average_country_risk=3.0)).loc[0, "customer_risk_score"] == 20
    assert score(features(average_country_risk=2.99)).loc[0, "customer_risk_score"] == 0


def test_high_value_count_indicator():
    assert score(features(high_value_tx_count=3)).loc[0, "customer_risk_score"] == 20
    assert score(features(high_value_tx_count=2)).loc[0, "customer_risk_score"] == 0


def test_velocity_indicator():
    assert score(features(velocity_24h=8)).loc[0, "customer_risk_score"] == 20
    assert score(features(velocity_24h=7)).loc[0, "customer_risk_score"] == 0


def test_pep_flag_and_kyc_review_add_their_own_points():
    result = score(features(), customers=customer_frame([{"customer_id": "C1", "pep_flag": 1}]))
    assert result.loc[0, "customer_risk_score"] == 15
    result = score(
        features(), customers=customer_frame([{"customer_id": "C1", "kyc_status": "Review Required"}])
    )
    assert result.loc[0, "customer_risk_score"] == 10


def test_all_indicators_combine_into_the_maximum_score():
    result = score(
        features(
            total_transaction_value=200_000.0,
            average_country_risk=4.0,
            high_value_tx_count=5,
            velocity_24h=10,
        ),
        customers=customer_frame([{"customer_id": "C1", "pep_flag": 1, "kyc_status": "Review Required"}]),
    )
    assert result.loc[0, "customer_risk_score"] == 105
    assert result.loc[0, "customer_risk_tier"] == "Critical"


@pytest.mark.parametrize(
    ("points", "expected_tier"),
    [(19, "Low"), (20, "Medium"), (39, "Medium"), (40, "High"), (69, "High"), (70, "Critical")],
)
def test_tier_boundaries(points, expected_tier):
    config = AnalysisConfig()
    tuned = replace(config, customer_scoring=replace(config.customer_scoring, pep_points=points))
    result = score(features(), customers=customer_frame([{"customer_id": "C1", "pep_flag": 1}]), config=tuned)
    assert result.loc[0, "customer_risk_tier"] == expected_tier


def test_customer_missing_from_the_customer_table_still_scores():
    result = score(features(), customers=customer_frame([{"customer_id": "C404"}]))
    assert result.loc[0, "customer_risk_score"] == 0
    assert result.loc[0, "customer_risk_tier"] == "Low"


def test_missing_feature_column_is_named():
    frame = features().drop(columns=["velocity_24h"])
    with pytest.raises(DataError) as error:
        score(frame)
    assert "velocity_24h" in str(error.value)


def test_scores_are_written_with_the_feature_and_tier_columns():
    result = score(features())
    assert list(result.columns)[-2:] == ["customer_risk_score", "customer_risk_tier"]


def test_top_customers_are_ordered_and_limited():
    frame = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3"],
            "customer_risk_score": [10, 70, 40],
            "customer_risk_tier": ["Low", "Critical", "High"],
            "total_transaction_value": [100.0, 300.0, 200.0],
            "high_value_tx_count": [0, 3, 1],
            "velocity_24h": [1, 9, 2],
        }
    )
    top = top_risky_customers(frame, 2)
    assert list(top["customer_id"]) == ["C2", "C3"]


@pytest.mark.parametrize("limit", [0, -1, 1.5, True, None])
def test_top_customers_reject_a_bad_limit(limit):
    frame = pd.DataFrame({"customer_id": ["C1"], "customer_risk_score": [10]})
    with pytest.raises(ValueError) as error:
        top_risky_customers(frame, limit)
    assert "limit" in str(error.value)


def test_top_customers_require_an_integer():
    frame = pd.DataFrame({"customer_id": ["C1"], "customer_risk_score": [10]})
    with pytest.raises(ValueError):
        top_risky_customers(frame, "3")
