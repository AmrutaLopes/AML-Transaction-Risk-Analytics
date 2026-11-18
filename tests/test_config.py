"""Configuration parsing and validation."""

from __future__ import annotations

import json
import math

import pytest

from aml import AnalysisConfig, ConfigError, config_from_mapping, load_config
from aml.config import CustomerScoringConfig, RuleConfig, TierConfig


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_match_the_published_thresholds():
    config = AnalysisConfig()
    assert config.rules.high_value_threshold == pytest.approx(10_000.0)
    assert config.rules.structuring_min_amount == pytest.approx(7_000.0)
    assert config.rules.structuring_max_amount == pytest.approx(9_999.99)
    assert config.rules.velocity_transaction_count == 8
    assert config.rules.alert_threshold == pytest.approx(30.0)
    assert config.tiers.labels == ("Low", "Medium", "High", "Critical")
    assert config.rules.max_risk_score == 120


def test_partial_override_keeps_the_other_defaults(tmp_path):
    path = write(tmp_path / "config.toml", "[rules]\nhigh_value_threshold = 20000\n")
    config = load_config(path)
    assert config.rules.high_value_threshold == pytest.approx(20_000.0)
    assert config.rules.structuring_max_amount == pytest.approx(9_999.99)
    assert config.rules.weight_pep == 20
    assert config.tiers.labels == ("Low", "Medium", "High", "Critical")


def test_json_configuration_is_accepted(tmp_path):
    payload = {"rules": {"velocity_transaction_count": 3}, "customer_scoring": {"pep_points": 5}}
    path = write(tmp_path / "config.json", json.dumps(payload))
    config = load_config(path)
    assert config.rules.velocity_transaction_count == 3
    assert config.customer_scoring.pep_points == 5


def test_example_configuration_in_the_repository_is_valid(project_root):
    config = load_config(project_root / "config" / "analysis.toml")
    assert config == AnalysisConfig(
        rules=RuleConfig(),
        customer_scoring=CustomerScoringConfig(),
        tiers=TierConfig(boundaries=(-1.0, 19.0, 39.0, 69.0, 999.0),
                         labels=("Low", "Medium", "High", "Critical")),
    )


def test_unknown_section_is_rejected():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rule": {"alert_threshold": 40}})
    assert "unknown configuration section" in str(error.value)
    assert "rules" in str(error.value)


def test_unknown_key_is_rejected_with_the_known_keys_listed():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"alert_threshhold": 40}})
    message = str(error.value)
    assert "alert_threshhold" in message
    assert "alert_threshold" in message


def test_negative_threshold_is_rejected_and_names_the_setting():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"high_value_threshold": -1}})
    message = str(error.value)
    assert "rules.high_value_threshold" in message
    assert "at least 0" in message


def test_boolean_is_not_accepted_as_a_number():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"alert_threshold": True}})
    assert "must be a number" in str(error.value)


def test_float_is_not_accepted_as_a_weight():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"weight_pep": 2.5}})
    assert "must be an integer" in str(error.value)


def test_zero_velocity_count_is_rejected():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"velocity_transaction_count": 0}})
    assert "at least 1" in str(error.value)


def test_invalid_velocity_window_is_rejected():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"velocity_window": "one hour"}})
    assert "not a valid duration" in str(error.value)


def test_structuring_band_must_increase():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"structuring_min_amount": 9000, "structuring_max_amount": 8000}})
    assert "structuring_min_amount" in str(error.value)


def test_unreachable_alert_threshold_is_rejected():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"rules": {"alert_threshold": 500}})
    assert "unreachable" in str(error.value)


def test_tier_labels_must_match_the_band_count():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"tiers": {"labels": ["Low", "High"]}})
    assert "one label per band" in str(error.value)


def test_tier_boundaries_must_increase_strictly():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"tiers": {"boundaries": [-1, 40, 30, 90]}})
    assert "increase strictly" in str(error.value)


def test_tiers_must_cover_zero():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"tiers": {"boundaries": [10, 20, 30, 40]}})
    assert "at or below 0" in str(error.value)


def test_tier_ceiling_must_sit_above_the_maximum_transaction_score():
    with pytest.raises(ConfigError) as error:
        config_from_mapping({"tiers": {"boundaries": [-1, 19, 39, 69, 90]}})
    assert "maximum transaction score" in str(error.value)


def test_configuration_to_dict_is_json_serialisable():
    payload = AnalysisConfig().to_dict()
    assert json.loads(json.dumps(payload))["tiers"]["boundaries"][-1] == 999.0


def test_custom_tiers_cover_a_score_above_the_default_ceiling():
    config = config_from_mapping({"tiers": {"boundaries": [-1, 19, 39, 69, math.inf]}})
    assert config.tiers.boundaries[-1] == math.inf


def test_missing_configuration_file_is_reported(tmp_path):
    with pytest.raises(ConfigError) as error:
        load_config(tmp_path / "nope.toml")
    assert "not found" in str(error.value)


def test_unsupported_extension_is_reported(tmp_path):
    path = write(tmp_path / "config.yaml", "rules: {}\n")
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "unsupported configuration format" in str(error.value)


def test_broken_toml_is_reported_with_the_file_name(tmp_path):
    path = write(tmp_path / "config.toml", "[rules\n")
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "config.toml" in str(error.value)


def test_configuration_dict_round_trips():
    payload = AnalysisConfig().to_dict()
    rebuilt = config_from_mapping(payload)
    assert rebuilt == AnalysisConfig()


def test_scoring_needs_a_tier_above_the_maximum_score():
    with pytest.raises(ConfigError) as error:
        config_from_mapping(
            {
                "customer_scoring": {"points_per_indicator": 40, "pep_points": 30, "kyc_review_points": 20},
                "tiers": {"boundaries": [-1, 19, 39, 69, 130]},
            }
        )
    assert "maximum customer score" in str(error.value)
