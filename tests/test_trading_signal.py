"""Tests du modèle TradingSignal."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from ecosystem_schemas import (
    Direction,
    Priority,
    SourceType,
    TradingSignal,
)
from pydantic import ValidationError


class TestFixturesParse:
    """Les 3 fixtures producteurs (IRIS / KRONOS / SMAUG) doivent parser sans erreur."""

    def test_iris_fixture(self, iris_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(iris_signal_payload)
        assert signal.signal_id == "IRIS-SOL-20250512-001"
        assert signal.asset == "SOL/USD"
        assert signal.source_meta.type == SourceType.IRIS_TELEGRAM
        assert signal.directional_bias.direction == Direction.BULLISH
        assert len(signal.entry_zones) == 2
        assert signal.entry_zones[0].priority == Priority.HIGH

    def test_kronos_fixture(self, kronos_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(kronos_signal_payload)
        assert signal.source_meta.type == SourceType.KRONOS_FORECAST
        assert signal.institutional_context is None
        assert signal.market_structure is None
        assert signal.source_meta.promo_bias == 0.0

    def test_smaug_fixture(self, smaug_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(smaug_signal_payload)
        assert signal.source_meta.type == SourceType.SMAUG_SMC
        assert signal.asset == "EUR/USD"
        assert signal.directional_bias.direction == Direction.BEARISH


class TestRoundtripJson:
    """Sérialisation JSON puis re-parsing doit être idempotent."""

    @pytest.mark.parametrize(
        "fixture_name",
        ["iris_signal_payload", "kronos_signal_payload", "smaug_signal_payload"],
    )
    def test_roundtrip(self, request: pytest.FixtureRequest, fixture_name: str) -> None:
        payload = request.getfixturevalue(fixture_name)
        signal = TradingSignal.model_validate(payload)
        serialized = signal.model_dump_json()
        reparsed = TradingSignal.model_validate_json(serialized)
        assert signal == reparsed


class TestImmutability:
    def test_frozen(self, iris_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(iris_signal_payload)
        with pytest.raises(ValidationError):
            signal.signal_id = "MUTATED"  # type: ignore[misc]


class TestValidation:
    """Cas d'invalidité — doivent lever ValidationError."""

    def test_naive_datetime_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["generated_at"] = "2025-05-12T08:00:00"  # naïf
        with pytest.raises(ValidationError, match="timezone-aware"):
            TradingSignal.model_validate(iris_signal_payload)

    def test_confidence_out_of_range(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["directional_bias"]["confidence"] = 1.5
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)

    def test_entry_zone_low_gt_high(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["entry_zones"][0]["low"] = "100.00"
        iris_signal_payload["entry_zones"][0]["high"] = "90.00"
        with pytest.raises(ValidationError, match="entry_zone.low"):
            TradingSignal.model_validate(iris_signal_payload)

    def test_unknown_source_type(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["source_meta"]["type"] = "unknown_source"
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)

    def test_extra_field_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["unexpected_field"] = "x"
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)

    def test_empty_entry_zones_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["entry_zones"] = []
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)

    def test_negative_price_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["invalidation"]["level"] = "-1.0"
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)

    def test_min_sources_below_one_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        iris_signal_payload["argos_instructions"]["min_sources_to_activate"] = 0
        with pytest.raises(ValidationError):
            TradingSignal.model_validate(iris_signal_payload)


class TestPrecision:
    """Les prix passent par Decimal, pas par float."""

    def test_decimal_preserved(self, iris_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(iris_signal_payload)
        assert isinstance(signal.entry_zones[0].low, Decimal)
        assert signal.entry_zones[0].low == Decimal("92.75")

    def test_decimal_from_string_avoids_float_drift(self) -> None:
        """0.1 + 0.2 = 0.30000000000000004 en float mais "0.30" en Decimal."""
        a = Decimal("0.1") + Decimal("0.2")
        assert a == Decimal("0.3")


class TestTzAware:
    def test_explicit_utc(self, iris_signal_payload: dict[str, Any]) -> None:
        signal = TradingSignal.model_validate(iris_signal_payload)
        assert signal.generated_at.tzinfo is not None
        assert signal.generated_at == datetime(2025, 5, 12, 7, 42, 0, tzinfo=UTC)
