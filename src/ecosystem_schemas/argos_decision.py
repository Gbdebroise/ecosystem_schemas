"""Schéma ArgosDecision — sortie ARGOS, entrée HERMES."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ecosystem_schemas.trading_signal import Direction


class ArgosStatus(StrEnum):
    """Statut de la décision ARGOS.

    - `activate` : exécute si AUTO, sinon propose + confirme
    - `standby`  : surveille, pas d'action immédiate
    - `conflict` : signaux contradictoires, alerte, aucune action
    - `reject`   : ignoré (filtre, dédup, invalidation)
    """

    ACTIVATE = "activate"
    STANDBY = "standby"
    CONFLICT = "conflict"
    REJECT = "reject"


class HermesAction(StrEnum):
    """Action demandée à HERMES."""

    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_POSITION = "close_position"
    HOLD = "hold"


class _FrozenModel(BaseModel):
    """Base immuable pour tous les sous-modèles."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class ArgosConsensus(_FrozenModel):
    """Consensus calculé par ARGOS sur les TradingSignal agrégés."""

    direction: Direction
    weighted_score: float = Field(ge=0.0, le=1.0)
    sources_count: int = Field(ge=0)
    sources_used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_sources_count_matches(self) -> ArgosConsensus:
        if self.sources_count != len(self.sources_used):
            msg = (
                f"sources_count ({self.sources_count}) != len(sources_used) "
                f"({len(self.sources_used)})"
            )
            raise ValueError(msg)
        return self


class HermesInstruction(_FrozenModel):
    """Instruction d'exécution à destination de HERMES."""

    action: HermesAction
    entry_low: Decimal | None = Field(default=None, gt=Decimal("0"))
    entry_high: Decimal | None = Field(default=None, gt=Decimal("0"))
    targets: list[Decimal] = Field(default_factory=list, max_length=10)
    stop_loss: Decimal | None = Field(default=None, gt=Decimal("0"))
    conviction: float = Field(ge=0.0, le=1.0)
    activation_condition: str | None = None

    @model_validator(mode="after")
    def _check_entry_zone_bounds(self) -> HermesInstruction:
        if (
            self.entry_low is not None
            and self.entry_high is not None
            and self.entry_low > self.entry_high
        ):
            msg = f"entry_low ({self.entry_low}) > entry_high ({self.entry_high})"
            raise ValueError(msg)
        return self


class ArgosDecision(_FrozenModel):
    """Décision finale produite par ARGOS et consommée par HERMES.

    Voir ADR-008 ARGOS (gate déterministe `ARGOS_RULES`).
    """

    decision_id: str = Field(min_length=1, max_length=128)
    status: ArgosStatus
    asset: str = Field(min_length=1, max_length=32)
    generated_at: datetime
    consensus: ArgosConsensus
    hermes_instruction: HermesInstruction

    @field_validator("generated_at")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "generated_at must be timezone-aware (UTC recommended)"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _check_status_action_coherence(self) -> ArgosDecision:
        action = self.hermes_instruction.action
        if self.status == ArgosStatus.ACTIVATE and action == HermesAction.HOLD:
            msg = "status=activate is inconsistent with action=hold"
            raise ValueError(msg)
        if self.status in {ArgosStatus.REJECT, ArgosStatus.CONFLICT} and action in {
            HermesAction.OPEN_LONG,
            HermesAction.OPEN_SHORT,
        }:
            msg = f"status={self.status} cannot have action={action}"
            raise ValueError(msg)
        return self
