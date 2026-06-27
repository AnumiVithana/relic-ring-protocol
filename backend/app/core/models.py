"""
Planet and Tower models.

Tower placement rules (from spec §6):
  - Towers sit on the planet's surface (at radius_km from center).
  - Equally spaced at angular intervals of (360 / active_towers) degrees.
  - Tower 0 starts at the TOP (positive y-axis, i.e. angle = 90° in math convention).
  - Indices increase CLOCKWISE, so each subsequent tower is rotated by
    -(360 / active_towers) degrees in standard math convention.

Coordinate convention:
  - Planet center is at (x_km, y_km) in absolute km space.
  - Tower (tx, ty) = center + radius * (sin θ, cos θ)
    where θ = -index * (2π / n) in radians (clockwise from top).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class Tower:
    planet_id: str
    index: int          # 0-based, clockwise from top
    x_km: float         # absolute position in km
    y_km: float

    def distance_to(self, other: "Tower") -> float:
        """Straight-line distance between two towers in km."""
        return math.hypot(self.x_km - other.x_km, self.y_km - other.y_km)

    def angle_rad(self, n_towers: int) -> float:
        """
        Angle of this tower measured from positive y-axis, clockwise.
        Used for arc-length calculations on the fiber ring.
        """
        return self.index * (2 * math.pi / n_towers)


@dataclass
class Planet:
    id: str
    codex: int                          # numerical base used for receiving
    x_km: float                         # center position in km (already scaled)
    y_km: float
    radius_km: float                    # NOT scaled — given directly in km
    active_towers: int
    atmosphere_thickness_km: float
    refraction_index: float
    towers: List[Tower] = field(default_factory=list)
    active: bool = True                 # set False to simulate node failure

    # ------------------------------------------------------------------ setup
    def __post_init__(self):
        self.towers = self._place_towers()

    def _place_towers(self) -> List[Tower]:
        """
        Place active_towers towers at equal intervals clockwise from the top.
        Tower i is at angle θ_i = i × (2π / n) measured clockwise from +y axis.

        In Cartesian (standard math axes, y-up):
            tx = cx + R × sin(θ_i)
            ty = cy + R × cos(θ_i)
        """
        n = self.active_towers
        towers = []
        for i in range(n):
            theta = i * (2 * math.pi / n)           # clockwise from +y
            tx = self.x_km + self.radius_km * math.sin(theta)
            ty = self.y_km + self.radius_km * math.cos(theta)
            towers.append(Tower(planet_id=self.id, index=i, x_km=tx, y_km=ty))
        return towers

    # ------------------------------------------------------------------ geometry
    @property
    def outer_radius_km(self) -> float:
        """Radius to outer edge of atmosphere."""
        return self.radius_km + self.atmosphere_thickness_km

    def arc_length_between_towers(self, t1: Tower, t2: Tower) -> float:
        """
        Shorter arc along the equatorial fiber ring between two towers on THIS planet.
        Arc length = R × min(Δθ, 2π − Δθ)
        """
        n = self.active_towers
        step = 2 * math.pi / n
        delta = abs(t1.index - t2.index) * step
        angle = min(delta, 2 * math.pi - delta)    # always take shorter arc
        return self.radius_km * angle

    def closest_tower_pair_to(
        self, other: "Planet"
    ) -> Tuple[Tower, Tower]:
        """
        Find the tower pair (one on self, one on other) that minimises
        straight-line void distance. Used for hop_log and fiber routing.
        Note: does NOT affect L calculation (which is center-to-center based).
        """
        best_dist = math.inf
        best_pair = (self.towers[0], other.towers[0])
        for t1 in self.towers:
            for t2 in other.towers:
                d = t1.distance_to(t2)
                if d < best_dist:
                    best_dist = d
                    best_pair = (t1, t2)
        return best_pair

    def get_tower(self, index: int) -> Tower:
        return self.towers[index]

    # ------------------------------------------------------------------ codec
    def encode_to_codex(self, ascii_values: List[int]) -> List[str]:
        """Convert a list of ASCII integers to this planet's base (codex)."""
        return [_int_to_base(v, self.codex) for v in ascii_values]

    def decode_from_codex(self, encoded: List[str]) -> List[int]:
        """Convert a list of codex strings back to ASCII integers."""
        return [int(s, self.codex) for s in encoded]

    # ------------------------------------------------------------------ repr
    def __repr__(self) -> str:
        status = "ACTIVE" if self.active else "DEAD"
        return (
            f"Planet({self.id!r}, codex={self.codex}, "
            f"towers={self.active_towers}, [{status}])"
        )


# ------------------------------------------------------------------ helpers

def _int_to_base(n: int, base: int) -> str:
    """
    Convert non-negative integer n to a string in the given base.
    Digits above 9 use uppercase letters: 10=A, 11=B, ...
    Matches the example in the spec: 72 in base 14 → '52', 72 in base 5 → '242'.
    """
    if base < 2:
        raise ValueError(f"Base must be >= 2, got {base}")
    if n == 0:
        return "0"
    digits = []
    while n:
        digits.append("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n % base])
        n //= base
    return "".join(reversed(digits))
