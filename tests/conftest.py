"""Fixtures partagées pour les tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def iris_signal_payload() -> dict[str, Any]:
    return _load_fixture("trading_signal_iris.json")


@pytest.fixture
def kronos_signal_payload() -> dict[str, Any]:
    return _load_fixture("trading_signal_kronos.json")


@pytest.fixture
def smaug_signal_payload() -> dict[str, Any]:
    return _load_fixture("trading_signal_smaug.json")


@pytest.fixture
def argos_decision_payload() -> dict[str, Any]:
    return _load_fixture("argos_decision_activate.json")
