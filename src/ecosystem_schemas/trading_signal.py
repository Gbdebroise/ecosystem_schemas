"""Schéma canonique TradingSignal — sortie IRIS/KRONOS/SMAUG, entrée ARGOS."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Direction(StrEnum):
    """Direction du biais directionnel ou du consensus."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Priority(StrEnum):
    """Priorité d'une entry zone ou d'un target."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceType(StrEnum):
    """Type de source ayant produit le TradingSignal.

    Utilisé par ARGOS pour pondérer les signaux dans `ARGOS_RULES`.
    """

    IRIS_TELEGRAM = "iris_telegram"
    IRIS_DISCORD = "iris_discord"
    IRIS_YOUTUBE = "iris_youtube"
    IRIS_ARTICLE = "iris_article"
    IRIS_NEWSLETTER = "iris_newsletter"
    KRONOS_FORECAST = "kronos_forecast"
    SMAUG_SMC = "smaug_smc"
    MANUAL = "manual"


class InvalidationType(StrEnum):
    """Type de niveau d'invalidation du signal."""

    STOP_LOSS = "stop_loss"
    SOFT_INVALIDATION = "soft_invalidation"
    TIME_INVALIDATION = "time_invalidation"


class _FrozenModel(BaseModel):
    """Base immuable pour tous les sous-modèles du schéma."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class DirectionalBias(_FrozenModel):
    """Biais directionnel du signal sur un horizon donné."""

    direction: Direction
    timeframe: str = Field(min_length=1, max_length=32)
    window_end: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class Trigger(_FrozenModel):
    """Trigger ayant déclenché le signal."""

    type: str = Field(min_length=1, max_length=64)
    confirmed: bool = False
    preceded_by: str | None = None
    description: str | None = None


class EntryZone(_FrozenModel):
    """Zone d'entrée possible."""

    id: str = Field(min_length=1, max_length=32)
    priority: Priority
    low: Decimal = Field(gt=Decimal("0"))
    high: Decimal = Field(gt=Decimal("0"))
    type: str = Field(min_length=1, max_length=32)
    rationale: str | None = None
    probability: float = Field(ge=0.0, le=1.0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_low_le_high(self) -> EntryZone:
        if self.low > self.high:
            msg = f"entry_zone.low ({self.low}) > entry_zone.high ({self.high})"
            raise ValueError(msg)
        return self


class Target(_FrozenModel):
    """Niveau cible (TP)."""

    id: str = Field(min_length=1, max_length=32)
    price: Decimal = Field(gt=Decimal("0"))
    type: str = Field(min_length=1, max_length=32)
    priority: Priority
    timeframe: str | None = None
    condition: str | None = None


class Invalidation(_FrozenModel):
    """Niveau d'invalidation du signal."""

    level: Decimal = Field(gt=Decimal("0"))
    type: InvalidationType
    consequence: str = Field(min_length=1, max_length=256)


class InstitutionalContext(_FrozenModel):
    """Contexte institutionnel (optionnel)."""

    notes: str | None = None
    liquidity_pools: list[Decimal] = Field(default_factory=list)
    order_blocks: list[Decimal] = Field(default_factory=list)


class MarketStructure(_FrozenModel):
    """Structure de marché (optionnel)."""

    htf_trend: Direction | None = None
    ltf_trend: Direction | None = None
    last_bos: Decimal | None = None
    last_choch: Decimal | None = None
    notes: str | None = None


class SourceMeta(_FrozenModel):
    """Métadonnées sur la source du signal.

    `author_id` est utilisé par ARGOS pour la déduplication (`dedup_key`) —
    le même analyste sur 2 canaux compte comme 1 source. Voir ADR-008 ARGOS.
    """

    type: SourceType
    methodology: str = Field(min_length=1, max_length=128)
    promo_bias: float = Field(ge=0.0, le=1.0)
    methodology_score: float = Field(ge=0.0, le=1.0)
    verifiability: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    author_id: str = Field(min_length=1, max_length=128)


class ArgosInstructions(_FrozenModel):
    """Instructions adressées à ARGOS par le producteur du signal."""

    cross_check_required: list[str] = Field(default_factory=list)
    min_sources_to_activate: int = Field(ge=1, le=10, default=2)
    hermes_activation_condition: str | None = None


class TradingSignal(_FrozenModel):
    """Format JSON canonique de signal trading partagé par tout l'écosystème.

    Producteurs : IRIS (extracteur texte), KRONOS (forecaster OHLCV), SMAUG (SMC/ICT).
    Consommateur : ARGOS (validateur multi-sources).

    Voir `ECOSYSTEM_ARCHITECTURE.md` section « Schéma canonique — TradingSignal ».
    """

    signal_id: str = Field(min_length=1, max_length=128)
    generated_at: datetime
    asset: str = Field(min_length=1, max_length=32)
    exchange_ref: str = Field(min_length=1, max_length=64)
    directional_bias: DirectionalBias
    trigger: Trigger
    entry_zones: list[EntryZone] = Field(min_length=1, max_length=10)
    targets: list[Target] = Field(min_length=1, max_length=10)
    invalidation: Invalidation
    institutional_context: InstitutionalContext | None = None
    market_structure: MarketStructure | None = None
    source_meta: SourceMeta
    argos_instructions: ArgosInstructions

    @field_validator("generated_at")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "generated_at must be timezone-aware (UTC recommended)"
            raise ValueError(msg)
        return value
