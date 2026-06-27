"""
Universe-level physical constants.
All values are read from universe_metadata in the config file.
Defaults listed here match the spec and are only used if a key is absent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseConstants:
    speed_of_light_km_s: float        # c  — default 300,000 km/s
    tower_delay_ms: float              # Δt — default 7 ms per tower hit
    lmax_km: float                     # max single void hop — default 50,000,000 km
    fiber_speed_fraction: float        # fraction of c for subsurface fiber — default 0.67
    coordinate_scale_unit_km: float    # multiply x/y coords to get km

    # ------------------------------------------------------------------ derived
    @property
    def fiber_speed_km_s(self) -> float:
        """Effective fiber propagation speed in km/s."""
        return self.fiber_speed_fraction * self.speed_of_light_km_s

    @property
    def tower_delay_s(self) -> float:
        """Tower delay converted to seconds for uniform latency math."""
        return self.tower_delay_ms / 1000.0

    # ------------------------------------------------------------------ factory
    @classmethod
    def from_dict(cls, meta: dict) -> "UniverseConstants":
        return cls(
            speed_of_light_km_s=meta.get("speed_of_light_km_s", 300_000),
            tower_delay_ms=meta.get("tower_delay_ms", 7),
            lmax_km=meta.get("lmax_km", 50_000_000),
            fiber_speed_fraction=meta.get("fiber_speed_fraction", 0.67),
            coordinate_scale_unit_km=meta.get("coordinate_scale_unit_km", 100_000),
        )
