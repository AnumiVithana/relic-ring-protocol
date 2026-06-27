"""
Loads and validates universe-config.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Documented defaults (used ONLY if the field is absent from universe_metadata)
# ---------------------------------------------------------------------------
DEFAULT_SPEED_OF_LIGHT_KMS = 300_000.0
DEFAULT_MAX_VOID_HOP_KM = 50_000_000.0
DEFAULT_TOWER_DELAY_MS = 7.0
DEFAULT_FIBER_SPEED_FRACTION = 0.67
DEFAULT_COORDINATE_SCALE_KM = 1.0  

MIN_ACTIVE_TOWERS = 4


class UniverseConfigError(ValueError):
    """Raised when universe-config.json is structurally invalid."""


@dataclass
class UniverseMetadata:
    system_name: str
    speed_of_light_kms: float = DEFAULT_SPEED_OF_LIGHT_KMS
    max_void_hop_distance_km: float = DEFAULT_MAX_VOID_HOP_KM
    coordinate_scale_unit_km: float = DEFAULT_COORDINATE_SCALE_KM
    tower_processing_delay_ms: float = DEFAULT_TOWER_DELAY_MS
    fiber_speed_fraction: float = DEFAULT_FIBER_SPEED_FRACTION

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "UniverseMetadata":
        return cls(
            system_name=raw.get("system_name", "Unknown System"),
            speed_of_light_kms=float(raw.get("speed_of_light_kms", DEFAULT_SPEED_OF_LIGHT_KMS)),
            max_void_hop_distance_km=float(
                raw.get("max_void_hop_distance_km", raw.get("Lmax", DEFAULT_MAX_VOID_HOP_KM))
            ),
            coordinate_scale_unit_km=float(
                raw.get("coordinate_scale_unit_km", DEFAULT_COORDINATE_SCALE_KM)
            ),
            tower_processing_delay_ms=float(
                raw.get("tower_processing_delay_ms", DEFAULT_TOWER_DELAY_MS)
            ),
            fiber_speed_fraction=float(
                raw.get("fiber_speed_fraction", DEFAULT_FIBER_SPEED_FRACTION)
            ),
        )


@dataclass
class PlanetConfig:
    id: str
    codex: int
    x: float
    y: float
    radius_km: float
    active_towers: int
    atmosphere_thickness_km: float
    refraction_index: float

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PlanetConfig":
        required = [
            "id", "codex", "x", "y", "radius_km",
            "active_towers", "atmosphere_thickness_km", "refraction_index",
        ]
        missing = [f for f in required if f not in raw]
        if missing:
            raise UniverseConfigError(
                f"Planet config missing required field(s): {missing} in {raw}"
            )

        active_towers = int(raw["active_towers"])
        if active_towers < MIN_ACTIVE_TOWERS:
            raise UniverseConfigError(
                f"Planet '{raw['id']}' has active_towers={active_towers}, "
                f"but the spec requires active_towers >= {MIN_ACTIVE_TOWERS}."
            )
        codex = int(raw["codex"])
        if codex < 2:
            raise UniverseConfigError(
                f"Planet '{raw['id']}' has codex={codex}; numeric base must be >= 2."
            )

        return cls(
            id=str(raw["id"]),
            codex=codex,
            x=float(raw["x"]),
            y=float(raw["y"]),
            radius_km=float(raw["radius_km"]),
            active_towers=active_towers,
            atmosphere_thickness_km=float(raw["atmosphere_thickness_km"]),
            refraction_index=float(raw["refraction_index"]),
        )


@dataclass
class UniverseConfig:
    metadata: UniverseMetadata
    planets: dict[str, PlanetConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "UniverseConfig":
        path = Path(path)
        if not path.exists():
            raise UniverseConfigError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            try:
                raw = json.load(f)
            except json.JSONDecodeError as e:
                raise UniverseConfigError(f"Invalid JSON in {path}: {e}") from e

        if "universe_metadata" not in raw:
            raise UniverseConfigError("Missing top-level 'universe_metadata' key.")
        if "nodes" not in raw or not isinstance(raw["nodes"], list) or not raw["nodes"]:
            raise UniverseConfigError("Missing or empty top-level 'nodes' array.")

        metadata = UniverseMetadata.from_dict(raw["universe_metadata"])

        planets: dict[str, PlanetConfig] = {}
        for node_raw in raw["nodes"]:
            planet = PlanetConfig.from_dict(node_raw)
            if planet.id in planets:
                raise UniverseConfigError(f"Duplicate planet id '{planet.id}' in config.")
            planets[planet.id] = planet

        if len(planets) < 2:
            raise UniverseConfigError("Universe must contain at least 2 planets to route between.")

        return cls(metadata=metadata, planets=planets)
