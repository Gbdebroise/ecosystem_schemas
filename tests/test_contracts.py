"""Tests de contrats inter-projets.

Ces tests garantissent que les fixtures canoniques de chaque producteur
(IRIS / KRONOS / SMAUG) restent valides et que les consommateurs (ARGOS,
HERMES) peuvent les consommer sans casse. Un échec ici signifie qu'un
changement de schéma peut casser un projet consommateur en aval.

Couvre :
- Round-trip JSON sans perte (sérialisation → reload → identité)
- Stabilité des enums (valeurs déclarées ne sont jamais retirées)
- Validations cross-modèle (consensus.sources_count, status↔action, entry_zone bounds)
- Tous les SourceType ont un fixture (au moins un cas réel par type)
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from ecosystem_schemas import (
    ArgosDecision,
    ArgosStatus,
    Direction,
    HermesAction,
    Priority,
    SourceType,
    TradingSignal,
)


def _json_round_trip(payload: dict[str, Any], model: type) -> Any:
    """Sérialise → JSON string → re-parse → valide. Renvoie l'instance finale."""
    instance = model.model_validate(payload)
    dumped = instance.model_dump_json()
    return model.model_validate_json(dumped)


class TestTradingSignalRoundTrip:
    """Le payload émis par IRIS/KRONOS/SMAUG doit round-tripper sans perte."""

    def test_iris_telegram_round_trip(self, iris_signal_payload: dict[str, Any]) -> None:
        reloaded = _json_round_trip(iris_signal_payload, TradingSignal)
        assert reloaded.source_meta.type == SourceType.IRIS_TELEGRAM
        # Décimaux : sensibles au float-int. Vérifie la précision.
        assert reloaded.entry_zones[0].low == Decimal("92.75")
        assert reloaded.invalidation.level == Decimal("87.00")

    def test_kronos_forecast_round_trip(self, kronos_signal_payload: dict[str, Any]) -> None:
        reloaded = _json_round_trip(kronos_signal_payload, TradingSignal)
        assert reloaded.source_meta.type == SourceType.KRONOS_FORECAST
        # KRONOS spécifique : pas de institutional_context ni market_structure
        assert reloaded.institutional_context is None
        assert reloaded.market_structure is None

    def test_smaug_smc_round_trip(self, smaug_signal_payload: dict[str, Any]) -> None:
        reloaded = _json_round_trip(smaug_signal_payload, TradingSignal)
        assert reloaded.source_meta.type == SourceType.SMAUG_SMC
        # SMAUG spécifique : market_structure typiquement renseigné
        assert reloaded.market_structure is not None


class TestArgosDecisionRoundTrip:
    def test_activate_decision_round_trip(self, argos_decision_payload: dict[str, Any]) -> None:
        reloaded = _json_round_trip(argos_decision_payload, ArgosDecision)
        assert reloaded.status == ArgosStatus.ACTIVATE
        assert reloaded.hermes_instruction.action in {
            HermesAction.OPEN_LONG,
            HermesAction.OPEN_SHORT,
        }


class TestEnumStability:
    """Les enums sont des contrats forts : aucune valeur ne doit disparaître sans bump majeur.

    Si ce test échoue, c'est qu'un consommateur (ARGOS, HERMES) qui mappait
    sur la valeur retirée va casser silencieusement. Toute suppression doit
    s'accompagner d'un incrément majeur de `ecosystem_schemas.__version__`.
    """

    SOURCE_TYPE_VALUES: frozenset[str] = frozenset(
        {
            "iris_telegram",
            "iris_discord",
            "iris_youtube",
            "iris_article",
            "iris_newsletter",
            "kronos_forecast",
            "smaug_smc",
            "manual",
        }
    )

    DIRECTION_VALUES: frozenset[str] = frozenset({"bullish", "bearish", "neutral"})
    PRIORITY_VALUES: frozenset[str] = frozenset({"high", "medium", "low"})
    ARGOS_STATUS_VALUES: frozenset[str] = frozenset({"activate", "standby", "conflict", "reject"})
    HERMES_ACTION_VALUES: frozenset[str] = frozenset(
        {"open_long", "open_short", "close_position", "hold"}
    )

    def test_source_type_stable(self) -> None:
        current = {member.value for member in SourceType}
        missing = self.SOURCE_TYPE_VALUES - current
        assert not missing, (
            f"SourceType perd des valeurs : {missing}. "
            f"Toute suppression doit bumper la version majeure de ecosystem_schemas."
        )

    def test_direction_stable(self) -> None:
        current = {member.value for member in Direction}
        assert current >= self.DIRECTION_VALUES

    def test_priority_stable(self) -> None:
        current = {member.value for member in Priority}
        assert current >= self.PRIORITY_VALUES

    def test_argos_status_stable(self) -> None:
        current = {member.value for member in ArgosStatus}
        assert current >= self.ARGOS_STATUS_VALUES

    def test_hermes_action_stable(self) -> None:
        current = {member.value for member in HermesAction}
        assert current >= self.HERMES_ACTION_VALUES


class TestCrossModelValidators:
    """Les invariants cross-modèles documentés dans les ADR doivent être enforced."""

    def test_consensus_sources_count_mismatch_rejected(
        self, argos_decision_payload: dict[str, Any]
    ) -> None:
        """ArgosConsensus.sources_count doit égaler len(sources_used)."""
        broken = json.loads(json.dumps(argos_decision_payload))
        broken["consensus"]["sources_count"] = 99  # mismatch volontaire
        with pytest.raises(ValueError, match="sources_count"):
            ArgosDecision.model_validate(broken)

    def test_status_activate_with_hold_action_rejected(
        self, argos_decision_payload: dict[str, Any]
    ) -> None:
        """status=activate + action=hold est incohérent (ADR cohérence statut↔action)."""
        broken = json.loads(json.dumps(argos_decision_payload))
        broken["hermes_instruction"]["action"] = "hold"
        with pytest.raises(ValueError, match="status=activate.*action=hold"):
            ArgosDecision.model_validate(broken)

    def test_status_reject_with_open_long_rejected(
        self, argos_decision_payload: dict[str, Any]
    ) -> None:
        """status=reject ne peut pas avoir une action d'ouverture."""
        broken = json.loads(json.dumps(argos_decision_payload))
        broken["status"] = "reject"
        broken["hermes_instruction"]["action"] = "open_long"
        with pytest.raises(ValueError, match="status=.*cannot have action"):
            ArgosDecision.model_validate(broken)

    def test_entry_zone_low_gt_high_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        """entry_zone.low > entry_zone.high doit échouer (validator EntryZone)."""
        broken = json.loads(json.dumps(iris_signal_payload))
        broken["entry_zones"][0]["low"] = "95.00"
        broken["entry_zones"][0]["high"] = "92.75"
        with pytest.raises(ValueError, match="entry_zone.low"):
            TradingSignal.model_validate(broken)

    def test_generated_at_naive_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        """generated_at doit être tz-aware (UTC) — la naïveté est rejetée."""
        broken = json.loads(json.dumps(iris_signal_payload))
        broken["generated_at"] = "2025-05-12T07:42:00"  # pas de tzinfo
        with pytest.raises(ValueError, match="timezone-aware"):
            TradingSignal.model_validate(broken)


class TestFixtureCoverage:
    """Chaque enum SourceType "actif" doit avoir au moins une fixture qui le couvre.

    `manual` est exempté (cas dégénéré, pas un producteur identifiable).
    Les futurs `iris_discord/youtube/article/newsletter` seront à ajouter
    quand le producteur correspondant arrive.
    """

    ACTIVE_PRODUCERS: frozenset[SourceType] = frozenset(
        {SourceType.IRIS_TELEGRAM, SourceType.KRONOS_FORECAST, SourceType.SMAUG_SMC}
    )

    def test_each_active_producer_has_a_fixture(
        self,
        iris_signal_payload: dict[str, Any],
        kronos_signal_payload: dict[str, Any],
        smaug_signal_payload: dict[str, Any],
    ) -> None:
        fixtures = [
            TradingSignal.model_validate(p)
            for p in (iris_signal_payload, kronos_signal_payload, smaug_signal_payload)
        ]
        covered = {s.source_meta.type for s in fixtures}
        missing = self.ACTIVE_PRODUCERS - covered
        assert not missing, (
            f"Producteurs actifs sans fixture round-trip : {missing}. "
            f"Ajouter une fixture dans tests/fixtures/."
        )


class TestForwardCompatibility:
    """Un consommateur conservateur ne doit pas casser si on ajoute un champ.

    Pydantic est strict (extra='forbid') sur les sous-modèles frozen — donc
    en pratique, ajouter un champ TOP-LEVEL à TradingSignal sans le déclarer
    dans le modèle casse. Le test ci-dessous documente cette propriété.
    """

    def test_unknown_top_level_field_rejected(self, iris_signal_payload: dict[str, Any]) -> None:
        broken = json.loads(json.dumps(iris_signal_payload))
        broken["future_field"] = "some value"
        with pytest.raises(ValueError, match="Extra inputs"):
            TradingSignal.model_validate(broken)
