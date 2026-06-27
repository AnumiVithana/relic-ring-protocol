"""
Tests for the latency engine.
Validates each component independently then checks totals.
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.universe import Universe
from app.core.models import Planet
from app.core.latency import LatencyEngine

CONFIG = os.path.join(os.path.dirname(__file__), "../../universe-config.json")


def get_universe():
    return Universe.load(CONFIG)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: build a controlled two-planet setup for formula verification
# ──────────────────────────────────────────────────────────────────────────────

def make_simple_pair():
    """
    Planet A at (0, 0),   R=1000 km, h=100 km, n=1.0, 4 towers
    Planet B at (0, scale) so center_dist = scale km after scaling.
    We bypass scaling here by setting x_km/y_km directly.
    """
    A = Planet(
        id="A", codex=10,
        x_km=0, y_km=0,
        radius_km=1000,
        active_towers=4,
        atmosphere_thickness_km=100,
        refraction_index=1.0,
    )
    # Place B far enough to be within Lmax but measurable
    # center_dist = 5_000_000 km
    B = Planet(
        id="B", codex=5,
        x_km=0, y_km=5_000_000,
        radius_km=800,
        active_towers=4,
        atmosphere_thickness_km=50,
        refraction_index=1.5,
    )
    return A, B


# ──────────────────────────────────────────────────────────────────────────────
# Void distance
# ──────────────────────────────────────────────────────────────────────────────

def test_void_distance_simple():
    """
    center_dist = 5,000,000 km
    L = 5,000,000 − (1000+100) − (800+50) = 5,000,000 − 1100 − 850 = 4,998,050 km
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()
    L = engine.void_distance(A, B)
    expected = 5_000_000 - (1000 + 100) - (800 + 50)
    assert abs(L - expected) < 1e-6

def test_void_distance_never_negative():
    """Overlapping planets should return L=0, not negative."""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()
    # Put B right on top of A
    B2 = Planet(
        id="B2", codex=5, x_km=0, y_km=0,
        radius_km=800, active_towers=4,
        atmosphere_thickness_km=50, refraction_index=1.0
    )
    assert engine.void_distance(A, B2) == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Atmosphere component
# ──────────────────────────────────────────────────────────────────────────────

def test_atm_no_refraction():
    """
    n=1.0 → signal travels at c through atmosphere.
    T_atm = h / c = 100 / 300_000 s
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()   # A has n=1.0, h=100

    # Use same tower for entry and send (T0) to isolate atmosphere
    send_tower = A.towers[0]
    recv_tower = B.towers[0]
    result = engine.compute(A, B, send_tower, send_tower, recv_tower)

    expected_atm_src = 100 / 300_000   # h/c in seconds
    assert abs(result.t_atm_src_s - expected_atm_src) < 1e-10

def test_atm_with_refraction():
    """
    B has n=1.5, h=50 → speed = c/1.5 → T_atm = 50 / (300_000/1.5) = 50×1.5/300_000
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    send_tower = A.towers[0]
    recv_tower = B.towers[0]
    result = engine.compute(A, B, send_tower, send_tower, recv_tower)

    expected_atm_dst = (50 * 1.5) / 300_000
    assert abs(result.t_atm_dst_s - expected_atm_dst) < 1e-10


# ──────────────────────────────────────────────────────────────────────────────
# Void transit
# ──────────────────────────────────────────────────────────────────────────────

def test_void_transit_time():
    """T_void = L / c"""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    send_tower = A.towers[0]
    recv_tower = B.towers[0]
    result = engine.compute(A, B, send_tower, send_tower, recv_tower)

    L = 5_000_000 - 1100 - 850
    expected = L / 300_000
    assert abs(result.t_void_s - expected) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Fiber component
# ──────────────────────────────────────────────────────────────────────────────

def test_fiber_zero_when_same_tower():
    """If entry tower == send tower, arc = 0, T_fiber = 0."""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    t0 = A.towers[0]
    result = engine.compute(A, B, t0, t0, B.towers[0])
    assert result.t_fiber_s == 0.0
    assert result.fiber_arc_km == 0.0

def test_fiber_adjacent_towers():
    """
    Entry=T0, Send=T1 on A (4 towers, R=1000 km).
    Arc = R × (2π/4) = 1000 × π/2
    T_fiber = arc / (0.67 × 300_000)
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    entry = A.towers[0]
    send  = A.towers[1]
    result = engine.compute(A, B, entry, send, B.towers[0])

    expected_arc = 1000 * (math.pi / 2)
    expected_t   = expected_arc / (0.67 * 300_000)
    assert abs(result.fiber_arc_km - expected_arc) < 1e-6
    assert abs(result.t_fiber_s - expected_t) < 1e-10

def test_fiber_uses_shorter_arc():
    """
    T0 to T3 on a 4-tower planet: shorter arc is 1 step (not 3 steps).
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    entry = A.towers[0]
    send  = A.towers[3]     # 3 steps clockwise OR 1 step counter-clockwise
    result = engine.compute(A, B, entry, send, B.towers[0])

    one_step_arc = 1000 * (math.pi / 2)
    assert abs(result.fiber_arc_km - one_step_arc) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Tower delay
# ──────────────────────────────────────────────────────────────────────────────

def test_tower_count_same_entry_send():
    """
    entry == send → 1 src tower + 1 recv tower = 2 towers hit.
    T_towers = 2 × 7ms = 14ms
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    t = A.towers[0]
    result = engine.compute(A, B, t, t, B.towers[0])
    assert result.towers_hit == 2
    assert abs(result.t_towers_ms - 14.0) < 1e-9

def test_tower_count_different_entry_send():
    """
    entry != send → 2 src towers + 1 recv tower = 3 towers hit.
    T_towers = 3 × 7ms = 21ms
    """
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    result = engine.compute(A, B, A.towers[0], A.towers[1], B.towers[0])
    assert result.towers_hit == 3
    assert abs(result.t_towers_ms - 21.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
# Lmax check
# ──────────────────────────────────────────────────────────────────────────────

def test_lmax_not_exceeded():
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()   # L ≈ 4,998,050 km < 50,000,000 km
    assert not engine.exceeds_lmax(A, B)

def test_lmax_exceeded():
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, _ = make_simple_pair()
    # Place B 600,000,000 km away — well beyond Lmax
    far_B = Planet(
        id="Far", codex=5, x_km=0, y_km=600_000_000,
        radius_km=800, active_towers=4,
        atmosphere_thickness_km=50, refraction_index=1.0
    )
    assert engine.exceeds_lmax(A, far_B)


# ──────────────────────────────────────────────────────────────────────────────
# Full hop total
# ──────────────────────────────────────────────────────────────────────────────

def test_total_is_sum_of_components():
    """Total latency must exactly equal the sum of all four components + towers."""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()

    result = engine.compute(A, B, A.towers[0], A.towers[1], B.towers[0])
    expected = (
        result.t_fiber_s
        + result.t_atm_src_s
        + result.t_void_s
        + result.t_atm_dst_s
        + result.t_towers_s
    )
    assert abs(result.total_s - expected) < 1e-12

def test_breakdown_dict_keys():
    """breakdown() must contain all required keys."""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    A, B = make_simple_pair()
    result = engine.compute(A, B, A.towers[0], A.towers[0], B.towers[0])
    b = result.breakdown()
    for key in ["fiber_ms","atm_src_ms","void_ms","atm_dst_ms","towers_ms","total_ms","towers_hit"]:
        assert key in b

def test_real_planets_aethon_to_boros():
    """Smoke test with actual config planets — just verify it runs and total > 0."""
    u = get_universe()
    engine = LatencyEngine(u.constants)
    src = u.get_planet("Aethon")
    dst = u.get_planet("Boros")
    send_t, recv_t = src.closest_tower_pair_to(dst)
    result = engine.compute(src, dst, send_t, send_t, recv_t)
    assert result.total_ms > 0
    print("\nAethon → Boros latency breakdown:")
    print(result)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
