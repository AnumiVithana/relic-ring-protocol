"""
Tests for config parser, planet model, and tower placement.
Run with: python -m pytest tests/ -v
"""

import math
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.universe import Universe
from app.core.models import Planet, _int_to_base


CONFIG = os.path.join(os.path.dirname(__file__), "../../universe-config.json")


# ────────────────────────────────────────────────────────────────
# Config loading
# ────────────────────────────────────────────────────────────────

def test_config_loads():
    u = Universe.load(CONFIG)
    assert len(u.planets) == 5
    assert "Aethon" in u.planets

def test_constants_parsed():
    u = Universe.load(CONFIG)
    c = u.constants
    assert c.speed_of_light_km_s == 300_000
    assert c.tower_delay_ms == 7
    assert c.lmax_km == 50_000_000
    assert c.fiber_speed_fraction == 0.67
    assert abs(c.fiber_speed_km_s - 201_000) < 1

def test_coordinate_scaling():
    u = Universe.load(CONFIG)
    # Boros is at x=3, y=1 in abstract units; scale = 100,000 km/unit
    boros = u.get_planet("Boros")
    assert boros.x_km == 300_000
    assert boros.y_km == 100_000

def test_radius_not_scaled():
    u = Universe.load(CONFIG)
    aethon = u.get_planet("Aethon")
    assert aethon.radius_km == 6000   # given in km, must not be multiplied


# ────────────────────────────────────────────────────────────────
# Tower placement
# ────────────────────────────────────────────────────────────────

def test_tower_count():
    u = Universe.load(CONFIG)
    aethon = u.get_planet("Aethon")
    assert len(aethon.towers) == 6

def test_tower_0_at_top():
    """Tower 0 must be directly above the planet center (positive y direction)."""
    u = Universe.load(CONFIG)
    aethon = u.get_planet("Aethon")
    t0 = aethon.towers[0]
    # Tower 0: angle=0 → sin(0)=0, cos(0)=1 → tx=cx, ty=cy+R
    assert abs(t0.x_km - aethon.x_km) < 1e-6
    assert abs(t0.y_km - (aethon.y_km + aethon.radius_km)) < 1e-6

def test_tower_spacing_equal():
    """Adjacent towers must be equidistant (equal chord lengths for uniform spacing)."""
    u = Universe.load(CONFIG)
    aethon = u.get_planet("Aethon")
    towers = aethon.towers
    n = len(towers)
    chord_0_1 = towers[0].distance_to(towers[1])
    chord_1_2 = towers[1].distance_to(towers[2])
    assert abs(chord_0_1 - chord_1_2) < 1e-6

def test_tower_on_surface():
    """Every tower must sit exactly at radius_km from the planet center."""
    u = Universe.load(CONFIG)
    for planet in u.all_planets():
        for tower in planet.towers:
            dist = math.hypot(tower.x_km - planet.x_km, tower.y_km - planet.y_km)
            assert abs(dist - planet.radius_km) < 1e-6, (
                f"{planet.id} tower {tower.index}: expected R={planet.radius_km}, got {dist:.4f}"
            )

def test_tower_clockwise_order():
    """
    For a planet with 4 towers, going 0→1→2→3 should rotate clockwise.
    In standard math coords (y-up), clockwise means decreasing angle from +y axis.
    Tower 0 is at top, Tower 1 should be to the right.
    """
    # Build a minimal planet centered at origin
    p = Planet(
        id="test", codex=10, x_km=0, y_km=0,
        radius_km=100, active_towers=4,
        atmosphere_thickness_km=10, refraction_index=1.0
    )
    t0, t1, t2, t3 = p.towers
    # T0 top: x≈0, y>0
    assert t0.x_km == 0 and t0.y_km == 100
    # T1 right: x>0, y≈0
    assert abs(t1.x_km - 100) < 1e-6 and abs(t1.y_km) < 1e-6
    # T2 bottom: x≈0, y<0
    assert abs(t2.x_km) < 1e-6 and abs(t2.y_km + 100) < 1e-6
    # T3 left: x<0, y≈0
    assert abs(t3.x_km + 100) < 1e-6 and abs(t3.y_km) < 1e-6


# ────────────────────────────────────────────────────────────────
# Arc length
# ────────────────────────────────────────────────────────────────

def test_arc_adjacent_towers():
    """Arc between adjacent towers = R × (2π/n)."""
    p = Planet(
        id="test", codex=10, x_km=0, y_km=0,
        radius_km=1000, active_towers=8,
        atmosphere_thickness_km=50, refraction_index=1.0
    )
    arc = p.arc_length_between_towers(p.towers[0], p.towers[1])
    expected = 1000 * (2 * math.pi / 8)
    assert abs(arc - expected) < 1e-6

def test_arc_shorter_path():
    """Arc between T0 and T7 on an 8-tower planet should use the short path (1 step, not 7)."""
    p = Planet(
        id="test", codex=10, x_km=0, y_km=0,
        radius_km=1000, active_towers=8,
        atmosphere_thickness_km=50, refraction_index=1.0
    )
    arc = p.arc_length_between_towers(p.towers[0], p.towers[7])
    one_step = 1000 * (2 * math.pi / 8)
    assert abs(arc - one_step) < 1e-6   # should NOT be 7 steps


# ────────────────────────────────────────────────────────────────
# Codec / base conversion (from spec §5 "Hello world" example)
# ────────────────────────────────────────────────────────────────

def test_base5_H():
    """ASCII 72 ('H') in base 5 must be '242' (per spec example)."""
    assert _int_to_base(72, 5) == "242"

def test_base14_H():
    """ASCII 72 ('H') in base 14 must be '52' (per spec example)."""
    assert _int_to_base(72, 14) == "52"

def test_full_hello_world_base5():
    """Full 'Hello world' payload in base 5 matches spec exactly."""
    msg = "Hello world"
    ascii_vals = [ord(c) for c in msg]
    result = [_int_to_base(v, 5) for v in ascii_vals]
    expected = ["242", "401", "413", "413", "421", "112", "434", "421", "424", "413", "400"]
    assert result == expected

def test_roundtrip_encode_decode():
    """Encoding then decoding a message should return original ASCII values."""
    p = Planet(
        id="test", codex=7, x_km=0, y_km=0,
        radius_km=500, active_towers=4,
        atmosphere_thickness_km=50, refraction_index=1.0
    )
    original = [ord(c) for c in "Relic Ring"]
    encoded = p.encode_to_codex(original)
    decoded = p.decode_from_codex(encoded)
    assert decoded == original


# ────────────────────────────────────────────────────────────────
# Void distance
# ────────────────────────────────────────────────────────────────

def test_void_distance_formula():
    """
    Two planets at x=0 and x=10 (abstract units), scale=100,000 km/unit.
    center_dist = 1,000,000 km.
    L = 1,000,000 − (R1+h1) − (R2+h2)
    """
    u = Universe.load(CONFIG)
    # Aethon (0,0), Boros (3,1) → center dist = sqrt(9+1) * 100000 = 316227.766 km
    aethon = u.get_planet("Aethon")
    boros = u.get_planet("Boros")
    L = u.void_distance_km(aethon, boros)
    center = math.hypot(300_000, 100_000)
    expected = center - (6000 + 200) - (4500 + 150)
    assert abs(L - expected) < 1

def test_lmax_enforced():
    """Planets within Lmax should allow direct hop."""
    u = Universe.load(CONFIG)
    # All planets in our sample config are within Lmax of each other
    assert u.can_direct_hop(u.get_planet("Aethon"), u.get_planet("Boros"))

def test_node_failure():
    u = Universe.load(CONFIG)
    u.kill_node("Boros")
    assert not u.get_planet("Boros").active
    assert not u.can_direct_hop(u.get_planet("Aethon"), u.get_planet("Boros"))
    u.restore_node("Boros")
    assert u.get_planet("Boros").active

def test_link_failure():
    u = Universe.load(CONFIG)
    u.kill_link("Aethon", "Boros")
    assert not u.is_link_alive("Aethon", "Boros")
    u.restore_link("Aethon", "Boros")
    assert u.is_link_alive("Aethon", "Boros")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
