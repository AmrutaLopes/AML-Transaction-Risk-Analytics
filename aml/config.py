"""Configuration objects for the AML transaction risk pipeline.

Every threshold, weight and risk tier used by the pipeline lives here so the
illustrative monitoring rules can be tuned without editing code.  The default
values reproduce the published portfolio results exactly.

A configuration file may be supplied as TOML or JSON.  Files are treated as
partial overrides: sections and keys that are not mentioned keep their
defaults, and any key that is not recognised raises :class:`ConfigError`
instead of being silently ignored.
"""

from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


class ConfigError(ValueError):
    """Raised when a configuration file or value is missing or invalid."""


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number(value: Any, name: str, *, minimum: float | None = None,
            strictly_greater: bool = False, allow_infinite: bool = False) -> float:
    if not _is_number(value):
        raise ConfigError(f"{name} must be a number, got {value!r}")
    number = float(value)
    if math.isnan(number):
        raise ConfigError(f"{name} must be a number, got {value!r}")
    if not allow_infinite and not math.isfinite(number):
        raise ConfigError(f"{name} must be finite, got {value!r}")
    if minimum is not None:
        if strictly_greater and number <= minimum:
            raise ConfigError(f"{name} must be greater than {minimum:g}, got {number:g}")
        if not strictly_greater and number < minimum:
            raise ConfigError(f"{name} must be at least {minimum:g}, got {number:g}")
    return number


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a non-empty string, got {value!r}")
    return value


def _string_sequence(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ConfigError(f"{name} must be a list of strings, got {value!r}")
    items = tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))
    if not items:
        raise ConfigError(f"{name} must not be empty")
    return items


def _number_sequence(value: Any, name: str) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ConfigError(f"{name} must be a list of numbers, got {value!r}")
    return tuple(
        _number(item, f"{name}[{index}]", allow_infinite=True)
        for index, item in enumerate(value)
    )


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierConfig:
    """Risk tier bands shared by transaction alerts and customer scores."""

    boundaries: tuple[float, ...] = (-1.0, 19.0, 39.0, 69.0, 999.0)
    labels: tuple[str, ...] = ("Low", "Medium", "High", "Critical")

    def __post_init__(self) -> None:
        boundaries = _number_sequence(list(self.boundaries), "tiers.boundaries")
        labels = _string_sequence(list(self.labels), "tiers.labels")
        for previous, current in zip(boundaries, boundaries[1:]):
            if not current > previous:
                raise ConfigError(
                    "tiers.boundaries must increase strictly, "
                    f"found {previous:g} followed by {current:g}"
                )
        if boundaries[0] > 0:
            raise ConfigError(
                f"tiers.boundaries must start at or below 0, got {boundaries[0]:g}"
            )
        if len(labels) != len(boundaries) - 1:
            raise ConfigError(
                "tiers.labels must contain exactly one label per band: "
                f"{len(boundaries) - 1} band(s) defined, {len(labels)} label(s) given"
            )
        if len(set(labels)) != len(labels):
            raise ConfigError("tiers.labels must be unique")
        object.__setattr__(self, "boundaries", boundaries)
        object.__setattr__(self, "labels", labels)


@dataclass(frozen=True)
class RuleConfig:
    """Thresholds and weights for the transaction monitoring rules."""

    high_value_threshold: float = 10_000.0
    structuring_min_amount: float = 7_000.0
    structuring_max_amount: float = 9_999.99
    structuring_transaction_type: str = "Cash Deposit"
    high_country_risk_threshold: float = 4.0
    velocity_window: str = "1h"
    velocity_transaction_count: int = 8
    pep_amount_threshold: float = 5_000.0
    weight_high_value: int = 25
    weight_structuring: int = 30
    weight_high_risk_country: int = 20
    weight_velocity: int = 25
    weight_pep: int = 20
    alert_threshold: float = 30.0

    def __post_init__(self) -> None:
        for name in (
            "high_value_threshold",
            "structuring_min_amount",
            "structuring_max_amount",
            "high_country_risk_threshold",
            "pep_amount_threshold",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), f"rules.{name}", minimum=0.0))
        if self.structuring_min_amount >= self.structuring_max_amount:
            raise ConfigError(
                "rules.structuring_min_amount must be below rules.structuring_max_amount, "
                f"got {self.structuring_min_amount:g} and {self.structuring_max_amount:g}"
            )
        object.__setattr__(
            self,
            "velocity_transaction_count",
            _integer(self.velocity_transaction_count, "rules.velocity_transaction_count", minimum=1),
        )
        object.__setattr__(self, "velocity_window", _text(self.velocity_window, "rules.velocity_window"))
        try:
            window = pd.Timedelta(self.velocity_window)
        except ValueError as error:
            raise ConfigError(
                f"rules.velocity_window is not a valid duration: {self.velocity_window!r}"
            ) from error
        if window <= pd.Timedelta(0):
            raise ConfigError(
                f"rules.velocity_window must be a positive duration, got {self.velocity_window!r}"
            )
        object.__setattr__(
            self,
            "structuring_transaction_type",
            _text(self.structuring_transaction_type, "rules.structuring_transaction_type"),
        )
        for name in (
            "weight_high_value",
            "weight_structuring",
            "weight_high_risk_country",
            "weight_velocity",
            "weight_pep",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), f"rules.{name}", minimum=0))
        if not any(getattr(self, name) for name in (
            "weight_high_value",
            "weight_structuring",
            "weight_high_risk_country",
            "weight_velocity",
            "weight_pep",
        )):
            raise ConfigError("rules must assign a non-zero weight to at least one rule")
        object.__setattr__(
            self,
            "alert_threshold",
            _number(self.alert_threshold, "rules.alert_threshold", minimum=0.0, strictly_greater=True),
        )

    @property
    def max_risk_score(self) -> int:
        return sum((
            self.weight_high_value,
            self.weight_structuring,
            self.weight_high_risk_country,
            self.weight_velocity,
            self.weight_pep,
        ))


@dataclass(frozen=True)
class CustomerScoringConfig:
    """Point values and cut-offs for the customer risk score."""

    total_value_threshold: float = 100_000.0
    average_country_risk_threshold: float = 3.0
    high_value_count_threshold: int = 3
    velocity_24h_threshold: int = 8
    points_per_indicator: int = 20
    pep_points: int = 15
    kyc_review_points: int = 10
    kyc_review_status: str = "Review Required"

    def __post_init__(self) -> None:
        for name in (
            "total_value_threshold",
            "average_country_risk_threshold",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), f"customer_scoring.{name}", minimum=0.0))
        for name in (
            "high_value_count_threshold",
            "velocity_24h_threshold",
            "points_per_indicator",
            "pep_points",
            "kyc_review_points",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), f"customer_scoring.{name}", minimum=0))
        object.__setattr__(
            self,
            "kyc_review_status",
            _text(self.kyc_review_status, "customer_scoring.kyc_review_status"),
        )
        if self.points_per_indicator <= 0:
            raise ConfigError("customer_scoring.points_per_indicator must be at least 1")
        if self.high_value_count_threshold < 1:
            raise ConfigError("customer_scoring.high_value_count_threshold must be at least 1")
        if self.velocity_24h_threshold < 1:
            raise ConfigError("customer_scoring.velocity_24h_threshold must be at least 1")

    @property
    def max_score(self) -> int:
        return 4 * self.points_per_indicator + self.pep_points + self.kyc_review_points


@dataclass(frozen=True)
class FeatureConfig:
    """Settings used while engineering customer and transaction features."""

    velocity_window: str = "24h"

    def __post_init__(self) -> None:
        window = _text(self.velocity_window, "features.velocity_window")
        try:
            parsed = pd.Timedelta(window)
        except ValueError as error:
            raise ConfigError(f"features.velocity_window is not a valid duration: {window!r}") from error
        if parsed <= pd.Timedelta(0):
            raise ConfigError(f"features.velocity_window must be a positive duration, got {window!r}")
        object.__setattr__(self, "velocity_window", window)


@dataclass(frozen=True)
class AnalysisConfig:
    """Top level configuration: one object passed through the whole pipeline."""

    rules: RuleConfig = RuleConfig()
    customer_scoring: CustomerScoringConfig = CustomerScoringConfig()
    tiers: TierConfig = TierConfig()
    features: FeatureConfig = FeatureConfig()

    def __post_init__(self) -> None:
        if self.rules.alert_threshold > self.rules.max_risk_score:
            raise ConfigError(
                "rules.alert_threshold is unreachable: the rules can score at most "
                f"{self.rules.max_risk_score}, got {self.rules.alert_threshold:g}"
            )
        ceiling = self.tiers.boundaries[-1]
        for label, maximum in (
            ("transaction", self.rules.max_risk_score),
            ("customer", self.customer_scoring.max_score),
        ):
            if maximum > ceiling:
                raise ConfigError(
                    f"tiers.boundaries stop at {ceiling:g}, below the maximum {label} score "
                    f"{maximum}; a score above the last boundary would have no tier"
                )

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return the configuration as plain, JSON serialisable data."""
        payload: dict[str, dict[str, Any]] = {}
        for section in fields(self):
            value = getattr(self, section.name)
            payload[section.name] = {
                item.name: list(item_value) if isinstance(item_value, tuple) else item_value
                for item in fields(value)
                for item_value in [getattr(value, item.name)]
            }
        return payload


SECTION_TYPES: dict[str, type] = {
    "rules": RuleConfig,
    "customer_scoring": CustomerScoringConfig,
    "tiers": TierConfig,
    "features": FeatureConfig,
}


def _section_from_mapping(section: str, payload: Mapping[str, Any]) -> Any:
    target = SECTION_TYPES[section]
    known = {item.name for item in fields(target)}
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ConfigError(
            f"unknown key(s) in [{section}]: {', '.join(unknown)}; "
            f"known keys are {', '.join(sorted(known))}"
        )
    values = dict(payload)
    if section == "tiers":
        for name in ("boundaries", "labels"):
            if name in values:
                values[name] = tuple(values[name])
    return target(**values)


def config_from_mapping(payload: Mapping[str, Any]) -> AnalysisConfig:
    """Build a configuration from nested overrides, validating the merged result."""
    if not isinstance(payload, Mapping):
        raise ConfigError(f"configuration must be a mapping, got {type(payload).__name__}")
    unknown = sorted(set(payload) - set(SECTION_TYPES))
    if unknown:
        raise ConfigError(
            f"unknown configuration section(s): {', '.join(unknown)}; "
            f"known sections are {', '.join(sorted(SECTION_TYPES))}"
        )
    sections: dict[str, Any] = {}
    for section in SECTION_TYPES:
        raw = payload.get(section, {})
        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise ConfigError(f"[{section}] must be a table, got {type(raw).__name__}")
        defaults = getattr(AnalysisConfig(), section)
        known = {item.name for item in fields(type(defaults))}
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ConfigError(
                f"unknown key(s) in [{section}]: {', '.join(unknown)}; "
                f"known keys are {', '.join(sorted(known))}"
            )
        merged = {name: getattr(defaults, name) for name in known}
        merged.update(dict(raw))
        sections[section] = _section_from_mapping(section, merged)
    return AnalysisConfig(**sections)


def load_config(path: str | Path | None = None) -> AnalysisConfig:
    """Load a configuration file, or return the defaults when *path* is None."""
    if path is None:
        return AnalysisConfig()
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"configuration file not found: {config_path}")
    suffix = config_path.suffix.lower()
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read configuration file {config_path}: {error}") from error
    try:
        if suffix == ".json":
            payload = json.loads(raw)
        elif suffix in {".toml", ".tml"}:
            payload = tomllib.loads(raw)
        else:
            raise ConfigError(
                f"unsupported configuration format {suffix!r} for {config_path}; "
                "use .toml or .json"
            )
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot parse configuration file {config_path}: {error}") from error
    try:
        return config_from_mapping(payload)
    except ConfigError as error:
        raise ConfigError(f"{config_path}: {error}") from error


DEFAULT_CONFIG = AnalysisConfig()
