# ecosystem_schemas

Schémas Pydantic v2 partagés de l'écosystème trading.

## Contenu

| Modèle | Producteurs | Consommateurs |
|---|---|---|
| `TradingSignal` | IRIS · KRONOS · SMAUG | ARGOS |
| `ArgosDecision` | ARGOS | HERMES |

Voir [ECOSYSTEM_ARCHITECTURE.md](../ECOSYSTEM_ARCHITECTURE.md) pour la vue d'ensemble.

## Installation (editable mode)

Depuis n'importe quel projet de l'écosystème (ARGOS, IRIS, HERMES, KRONOS, SMAUG) :

```bash
uv add --editable ../ecosystem_schemas
```

Ou via `pyproject.toml` :

```toml
[project]
dependencies = [
    "ecosystem_schemas",
]

[tool.uv.sources]
ecosystem_schemas = { path = "../ecosystem_schemas", editable = true }
```

## Usage

```python
from ecosystem_schemas import TradingSignal, ArgosDecision

# Validation côté producteur (IRIS/KRONOS/SMAUG)
signal = TradingSignal.model_validate(payload)

# Validation côté consommateur (ARGOS)
signal = TradingSignal.model_validate_json(raw_body)

# Sérialisation HTTP
payload = signal.model_dump(mode="json")
```

## Tests

```bash
uv sync --extra dev
uv run pytest
```

Coverage cible : ≥ 80%.

## Versionning

Tous les producteurs et consommateurs doivent pinner la même version mineure
(`ecosystem_schemas==0.1.*`). Toute breaking change → bump mineur + migration
coordonnée des consommateurs.

## Standards

- Pydantic v2, modèles **frozen** (immuables)
- `Decimal` pour les prix (pas de `float` qui perd la précision)
- `datetime` aware (UTC) — jamais de naïfs
- Enums explicites (StrEnum) pour `direction`, `status`, `source_type`, etc.
- Type hints stricts, mypy clean
