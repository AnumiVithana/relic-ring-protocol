
from __future__ import annotations

import math

from app.config import PlanetConfig


def void_distance_km(
    planet_a: PlanetConfig,
    planet_b: PlanetConfig,
    coordinate_scale_km: float,
) -> float:
    """L - vacuum gap between the outer edges of two planets' atmospheres."""
    center_dist_units = math.hypot(planet_a.x - planet_b.x, planet_a.y - planet_b.y)
    center_dist_km = center_dist_units * coordinate_scale_km

    return (
        center_dist_km
        - (planet_a.radius_km + planet_a.atmosphere_thickness_km)
        - (planet_b.radius_km + planet_b.atmosphere_thickness_km)
    )


def void_travel_time_s(
    planet_a: PlanetConfig,
    planet_b: PlanetConfig,
    L_km: float,
    speed_of_light_kms: float,
) -> float:
    """T_v - laser transit time including atmospheric refraction slowdown."""
    numerator = (
        planet_a.atmosphere_thickness_km * planet_a.refraction_index
        + planet_b.atmosphere_thickness_km * planet_b.refraction_index
        + L_km
    )
    return numerator / speed_of_light_kms


def crust_transit_time_s(
    planet: PlanetConfig,
    angular_separation_deg: float,
    same_tower: bool,
    fiber_speed_fraction: float,
    speed_of_light_kms: float,
    tower_processing_delay_ms: float,
) -> float:
    """
    T_p - time spent routing internally on a planet between an entry tower
    and an exit tower (fiber arc) plus per-distinct-tower processing delay.

    For origin/destination planets, call with angular_separation_deg=0.0 and
    same_tower=True (single tower touched, no arc to travel).
    """
    dt_s = tower_processing_delay_ms / 1000.0
    if same_tower:
        m = 1
    else:
        # Calculate number of segments: s = angular_separation_deg / (360.0 / N)
        s = round(angular_separation_deg / (360.0 / planet.active_towers))
        m = s + 1

    arc_fraction = angular_separation_deg / 360.0
    circumference_km = 2 * math.pi * planet.radius_km
    arc_distance_km = circumference_km * arc_fraction

    fiber_time_s = arc_distance_km / (fiber_speed_fraction * speed_of_light_kms)
    processing_time_s = m * dt_s

    return fiber_time_s + processing_time_s


def seconds_to_ms(seconds: float) -> float:
    return seconds * 1000.0
