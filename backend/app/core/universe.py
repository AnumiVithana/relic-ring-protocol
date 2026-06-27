"""
Universe config parser.

Reads universe-config.json and produces:
  - UniverseConstants  (physical constants from universe_metadata)
  - Dict[str, Planet]  (all planet nodes with towers placed)

Usage:
    universe = Universe.load("universe-config.json")
    planet = universe.get_planet("Aethon")
    print(planet.towers)
"""

import json
import math
from pathlib import Path
from typing import Dict, Optional

from .constants import UniverseConstants
from .models import Planet


class Universe:
    """
    Central model of the star system.
    Holds all planets and physical constants parsed from config.
    """

    def __init__(self, constants: UniverseConstants, planets: Dict[str, Planet]):
        self.constants = constants
        self.planets: Dict[str, Planet] = planets
        self._failed_nodes: set = set()
        self._failed_links: set = set()     # stored as frozenset({id_a, id_b})

    # ------------------------------------------------------------------ factory
    @classmethod
    def load(cls, config_path: str | Path) -> "Universe":
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")

        with open(path) as f:
            raw = json.load(f)

        constants = UniverseConstants.from_dict(raw.get("universe_metadata", {}))
        planets = {}

        for p in raw.get("planets", []):
            # Scale x/y from abstract units to km; radius_km is already in km
            x_km = p["x"] * constants.coordinate_scale_unit_km
            y_km = p["y"] * constants.coordinate_scale_unit_km

            planet = Planet(
                id=p["id"],
                codex=p["codex"],
                x_km=x_km,
                y_km=y_km,
                radius_km=p["radius_km"],
                active_towers=p["active_towers"],
                atmosphere_thickness_km=p["atmosphere_thickness_km"],
                refraction_index=p["refraction_index"],
            )
            planets[planet.id] = planet

        return cls(constants, planets)

    # ------------------------------------------------------------------ lookup
    def get_planet(self, planet_id: str) -> Planet:
        if planet_id not in self.planets:
            raise KeyError(f"Unknown planet: {planet_id!r}")
        return self.planets[planet_id]

    def all_planets(self) -> list[Planet]:
        return list(self.planets.values())

    def active_planets(self) -> list[Planet]:
        return [p for p in self.planets.values() if p.active]

    # ------------------------------------------------------------------ failure simulation
    def kill_node(self, planet_id: str):
        """Mark a planet as dead (simulates node failure)."""
        planet = self.get_planet(planet_id)
        planet.active = False
        self._failed_nodes.add(planet_id)
        print(f"[CHAOS] Node '{planet_id}' killed.")

    def kill_link(self, planet_id_a: str, planet_id_b: str):
        """Mark a direct link between two planets as dead."""
        link = frozenset({planet_id_a, planet_id_b})
        self._failed_links.add(link)
        print(f"[CHAOS] Link '{planet_id_a}' ↔ '{planet_id_b}' severed.")

    def restore_node(self, planet_id: str):
        planet = self.get_planet(planet_id)
        planet.active = True
        self._failed_nodes.discard(planet_id)
        print(f"[RESTORE] Node '{planet_id}' restored.")

    def restore_link(self, planet_id_a: str, planet_id_b: str):
        link = frozenset({planet_id_a, planet_id_b})
        self._failed_links.discard(link)
        print(f"[RESTORE] Link '{planet_id_a}' ↔ '{planet_id_b}' restored.")

    def is_link_alive(self, planet_id_a: str, planet_id_b: str) -> bool:
        return frozenset({planet_id_a, planet_id_b}) not in self._failed_links

    # ------------------------------------------------------------------ geometry helpers
    def void_distance_km(self, planet_a: Planet, planet_b: Planet) -> float:
        """
        L = center_to_center × scale − (R₁ + h₁) − (R₂ + h₂)
        Note: x_km/y_km are already scaled; radius and atm are in km as-is.
        """
        center_dist = math.hypot(
            planet_a.x_km - planet_b.x_km,
            planet_a.y_km - planet_b.y_km,
        )
        L = center_dist - planet_a.outer_radius_km - planet_b.outer_radius_km
        return max(L, 0.0)  # can't be negative (overlapping planets)

    def can_direct_hop(self, planet_a: Planet, planet_b: Planet) -> bool:
        """True if the void distance between two planets is within Lmax."""
        if not planet_a.active or not planet_b.active:
            return False
        if not self.is_link_alive(planet_a.id, planet_b.id):
            return False
        return self.void_distance_km(planet_a, planet_b) <= self.constants.lmax_km

    # ------------------------------------------------------------------ summary
    def summary(self) -> str:
        lines = [
            "=== Universe Summary ===",
            f"  c          = {self.constants.speed_of_light_km_s:,} km/s",
            f"  fiber      = {self.constants.fiber_speed_km_s:,.0f} km/s ({self.constants.fiber_speed_fraction}c)",
            f"  tower Δt   = {self.constants.tower_delay_ms} ms",
            f"  L_max      = {self.constants.lmax_km:,} km",
            f"  scale      = {self.constants.coordinate_scale_unit_km:,} km/unit",
            f"  planets    = {len(self.planets)}",
            "",
        ]
        for p in self.planets.values():
            status = "✓" if p.active else "✗ DEAD"
            lines.append(
                f"  [{status}] {p.id:<12} codex={p.codex:<3} "
                f"towers={p.active_towers}  "
                f"pos=({p.x_km/1e6:.2f}, {p.y_km/1e6:.2f}) Mkm  "
                f"R={p.radius_km} km  atm={p.atmosphere_thickness_km} km  n={p.refraction_index}"
            )
        return "\n".join(lines)
