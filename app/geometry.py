
from __future__ import annotations

import math
from dataclasses import dataclass

from app.config import PlanetConfig


@dataclass(frozen=True)
class TowerPosition:
    planet_id: str
    index: int
    angle_deg: float  
    x_km: float  
    y_km: float


def tower_angle_deg(index: int, active_towers: int) -> float:
    """Angle (deg, clockwise from top) of tower `index` out of `active_towers`."""
    return (360.0 / active_towers) * index


def tower_world_position(
    planet: PlanetConfig,
    index: int,
    coordinate_scale_km: float,
) -> TowerPosition:
    """
    Absolute world position (km) of a tower on a planet's surface.

    Planet center is at (planet.x, planet.y) * coordinate_scale_km.
    Tower sits on the circumference at radius_km from that center, at the
    angle for `index`, measured clockwise from the top.

    Standard screen/world convention used here: clockwise-from-top with a
    right-handed (x right, y up) coordinate system means:
        dx = R * sin(theta)
        dy = R * cos(theta)
    """
    theta_deg = tower_angle_deg(index, planet.active_towers)
    theta_rad = math.radians(theta_deg)

    center_x = planet.x * coordinate_scale_km
    center_y = planet.y * coordinate_scale_km

    dx = planet.radius_km * math.sin(theta_rad)
    dy = planet.radius_km * math.cos(theta_rad)

    return TowerPosition(
        planet_id=planet.id,
        index=index,
        angle_deg=theta_deg,
        x_km=center_x + dx,
        y_km=center_y + dy,
    )


def all_tower_positions(
    planet: PlanetConfig, coordinate_scale_km: float
) -> list[TowerPosition]:
    return [
        tower_world_position(planet, i, coordinate_scale_km)
        for i in range(planet.active_towers)
    ]


def straight_line_distance_km(a: TowerPosition, b: TowerPosition) -> float:
    return math.hypot(a.x_km - b.x_km, a.y_km - b.y_km)


def closest_tower_pair(
    planet_a: PlanetConfig,
    planet_b: PlanetConfig,
    coordinate_scale_km: float,
) -> tuple[TowerPosition, TowerPosition, float]:
    """
    Line-of-sight rule - find the tower on planet_a and the tower on planet_b
    whose straight-line distance is minimized. Returns (tower_a, tower_b,
    distance_km). This distance is used ONLY to pick the tower pair -- the
    actual void distance L used in latency math comes from the simplified
    center-to-center formula (see latency.py), per the spec's "Void Distance
    Simplification" note.
    """
    towers_a = all_tower_positions(planet_a, coordinate_scale_km)
    towers_b = all_tower_positions(planet_b, coordinate_scale_km)

    best: tuple[TowerPosition, TowerPosition, float] | None = None
    for ta in towers_a:
        for tb in towers_b:
            d = straight_line_distance_km(ta, tb)
            if best is None or d < best[2]:
                best = (ta, tb, d)
    assert best is not None
    return best


def angular_separation_deg(angle_a_deg: float, angle_b_deg: float) -> float:
    """Shortest angular separation between two angles on a circle, in [0, 180]."""
    diff = abs(angle_a_deg - angle_b_deg) % 360.0
    return min(diff, 360.0 - diff)


def arc_segments_between(
    tower_a_index: int, tower_b_index: int, active_towers: int
) -> int:
    """
    Number of tower-to-tower segments along the shortest arc direction
    between two tower indices on the same ring (used for documentation /
    hop_log; the actual T_p formula uses the continuous angular separation).
    """
    diff = abs(tower_a_index - tower_b_index) % active_towers
    return min(diff, active_towers - diff)
