import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import PlanetConfig
from app.latency import crust_transit_time_s, void_distance_km, void_travel_time_s


def make_planet(**overrides):
    base = dict(
        id="X", codex=10, x=0.0, y=0.0, radius_km=1000.0,
        active_towers=4, atmosphere_thickness_km=50.0, refraction_index=1.0,
    )
    base.update(overrides)
    return PlanetConfig(**base)


def test_void_distance_simple_case():
    a = make_planet(id="A", x=0.0, y=0.0, radius_km=100.0, atmosphere_thickness_km=10.0)
    b = make_planet(id="B", x=3.0, y=4.0, radius_km=50.0, atmosphere_thickness_km=5.0)
    L = void_distance_km(a, b, coordinate_scale_km=1000.0)
    expected = 5000.0 - (100 + 10) - (50 + 5)
    assert math.isclose(L, expected)


def test_void_travel_time_includes_refraction_and_void():
    a = make_planet(id="A", atmosphere_thickness_km=10.0, refraction_index=1.5)
    b = make_planet(id="B", atmosphere_thickness_km=20.0, refraction_index=2.0)
    L = 1000.0
    C = 300000.0
    tv = void_travel_time_s(a, b, L, C)
    expected = (10 * 1.5 + 20 * 2.0 + 1000.0) / C
    assert math.isclose(tv, expected)


def test_crust_transit_origin_or_destination_is_single_delay():
    planet = make_planet(radius_km=5000.0)
    t_p = crust_transit_time_s(
        planet, angular_separation_deg=0.0, same_tower=True,
        fiber_speed_fraction=0.67, speed_of_light_kms=300000.0,
        tower_processing_delay_ms=7.0,
    )
    assert math.isclose(t_p, 0.007)


def test_crust_transit_relay_includes_arc_and_two_delays():
    planet = make_planet(radius_km=6371.0)
    s = 90.0
    t_p = crust_transit_time_s(
        planet, angular_separation_deg=s, same_tower=False,
        fiber_speed_fraction=0.67, speed_of_light_kms=300000.0,
        tower_processing_delay_ms=7.0,
    )
    circumference = 2 * math.pi * 6371.0
    arc = circumference * (90.0 / 360.0)
    expected_fiber_s = arc / (0.67 * 300000.0)
    expected_total = expected_fiber_s + 2 * 0.007
    assert math.isclose(t_p, expected_total)


if __name__ == "__main__":
    test_void_distance_simple_case()
    test_void_travel_time_includes_refraction_and_void()
    test_crust_transit_origin_or_destination_is_single_delay()
    test_crust_transit_relay_includes_arc_and_two_delays()
    print("All latency tests passed.")
