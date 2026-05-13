"""Schémas Pydantic partagés de l'écosystème trading."""

from ecosystem_schemas.argos_decision import (
    ArgosConsensus,
    ArgosDecision,
    ArgosStatus,
    HermesAction,
    HermesInstruction,
)
from ecosystem_schemas.trading_signal import (
    ArgosInstructions,
    Direction,
    DirectionalBias,
    EntryZone,
    InstitutionalContext,
    Invalidation,
    InvalidationType,
    MarketStructure,
    Priority,
    SourceMeta,
    SourceType,
    Target,
    TradingSignal,
    Trigger,
)

__version__ = "0.1.0"

__all__ = [
    "ArgosConsensus",
    "ArgosDecision",
    "ArgosInstructions",
    "ArgosStatus",
    "Direction",
    "DirectionalBias",
    "EntryZone",
    "HermesAction",
    "HermesInstruction",
    "InstitutionalContext",
    "Invalidation",
    "InvalidationType",
    "MarketStructure",
    "Priority",
    "SourceMeta",
    "SourceType",
    "Target",
    "TradingSignal",
    "Trigger",
    "__version__",
]
