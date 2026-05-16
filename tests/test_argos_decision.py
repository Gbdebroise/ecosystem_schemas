"""Tests du modèle ArgosDecision."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ecosystem_schemas import (
    ArgosDecision,
    ArgosStatus,
    Direction,
    HermesAction,
)


class TestFixtureParse:
    def test_activate_fixture(self, argos_decision_payload: dict[str, Any]) -> None:
        decision = ArgosDecision.model_validate(argos_decision_payload)
        assert decision.status == ArgosStatus.ACTIVATE
        assert decision.consensus.direction == Direction.BULLISH
        assert decision.consensus.sources_count == 3
        assert decision.hermes_instruction.action == HermesAction.OPEN_LONG


class TestRoundtripJson:
    def test_roundtrip(self, argos_decision_payload: dict[str, Any]) -> None:
        decision = ArgosDecision.model_validate(argos_decision_payload)
        serialized = decision.model_dump_json()
        reparsed = ArgosDecision.model_validate_json(serialized)
        assert decision == reparsed


class TestImmutability:
    def test_frozen(self, argos_decision_payload: dict[str, Any]) -> None:
        decision = ArgosDecision.model_validate(argos_decision_payload)
        with pytest.raises(ValidationError):
            decision.decision_id = "MUTATED"  # type: ignore[misc]


class TestConsensusValidation:
    def test_sources_count_mismatch(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["consensus"]["sources_count"] = 5  # mais sources_used a 3 éléments
        with pytest.raises(ValidationError, match="sources_count"):
            ArgosDecision.model_validate(argos_decision_payload)

    def test_weighted_score_out_of_range(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["consensus"]["weighted_score"] = 1.5
        with pytest.raises(ValidationError):
            ArgosDecision.model_validate(argos_decision_payload)


class TestStatusActionCoherence:
    def test_activate_hold_rejected(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["hermes_instruction"]["action"] = "hold"
        with pytest.raises(ValidationError, match="inconsistent"):
            ArgosDecision.model_validate(argos_decision_payload)

    def test_reject_with_open_long_rejected(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["status"] = "reject"
        with pytest.raises(ValidationError, match="cannot have action"):
            ArgosDecision.model_validate(argos_decision_payload)

    def test_standby_hold_ok(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["status"] = "standby"
        argos_decision_payload["hermes_instruction"]["action"] = "hold"
        decision = ArgosDecision.model_validate(argos_decision_payload)
        assert decision.status == ArgosStatus.STANDBY
        assert decision.hermes_instruction.action == HermesAction.HOLD


class TestHermesInstructionBounds:
    def test_entry_low_gt_high_rejected(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["hermes_instruction"]["entry_low"] = "100.00"
        argos_decision_payload["hermes_instruction"]["entry_high"] = "90.00"
        with pytest.raises(ValidationError, match="entry_low"):
            ArgosDecision.model_validate(argos_decision_payload)

    def test_entry_low_none_ok(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["hermes_instruction"]["entry_low"] = None
        argos_decision_payload["hermes_instruction"]["entry_high"] = None
        decision = ArgosDecision.model_validate(argos_decision_payload)
        assert decision.hermes_instruction.entry_low is None


class TestEnums:
    @pytest.mark.parametrize("status_str", ["activate", "standby", "conflict", "reject"])
    def test_all_argos_statuses(
        self,
        argos_decision_payload: dict[str, Any],
        status_str: str,
    ) -> None:
        argos_decision_payload["status"] = status_str
        if status_str in {"reject", "conflict"}:
            argos_decision_payload["hermes_instruction"]["action"] = "hold"
        decision = ArgosDecision.model_validate(argos_decision_payload)
        assert decision.status == ArgosStatus(status_str)

    def test_unknown_status_rejected(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["status"] = "unknown_status"
        with pytest.raises(ValidationError):
            ArgosDecision.model_validate(argos_decision_payload)


class TestTzAware:
    def test_naive_datetime_rejected(self, argos_decision_payload: dict[str, Any]) -> None:
        argos_decision_payload["generated_at"] = "2025-05-12T08:00:00"
        with pytest.raises(ValidationError, match="timezone-aware"):
            ArgosDecision.model_validate(argos_decision_payload)
