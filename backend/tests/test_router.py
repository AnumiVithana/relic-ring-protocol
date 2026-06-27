"""
Tests for the routing engine.
Covers: shortest path, encoding, dead nodes, dead links, undeliverable routes.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.universe import Universe
from app.core.router import Router
from app.core.models import _int_to_base

CONFIG = os.path.join(os.path.dirname(__file__), "../../universe-config.json")


def get_router():
    u = Universe.load(CONFIG)
    return Router(u), u


# ──────────────────────────────────────────────────────────────────────────────
# Basic routing
# ──────────────────────────────────────────────────────────────────────────────

def test_same_planet_no_hops():
    router, _ = get_router()
    result = router.route("Aethon", "Aethon", "test")
    assert not result.undeliverable
    assert result.path == ["Aethon"]
    assert result.total_latency_ms == 0.0
    assert len(result.hop_log) == 0

def test_direct_hop_exists():
    router, _ = get_router()
    result = router.route("Aethon", "Boros", "Hello")
    assert not result.undeliverable
    assert len(result.path) >= 2
    assert result.path[0] == "Aethon"
    assert result.path[-1] == "Boros"

def test_path_starts_at_origin_ends_at_destination():
    router, _ = get_router()
    result = router.route("Aethon", "Cyra", "Hi")
    assert not result.undeliverable
    assert result.path[0] == "Aethon"
    assert result.path[-1] == "Cyra"

def test_total_latency_positive():
    router, _ = get_router()
    result = router.route("Aethon", "Cyra", "Hello world")
    assert result.total_latency_ms > 0

def test_hop_log_length_matches_path():
    router, _ = get_router()
    result = router.route("Aethon", "Cyra", "test")
    assert len(result.hop_log) == len(result.path) - 1

def test_hop_log_step_numbers():
    router, _ = get_router()
    result = router.route("Aethon", "Cyra", "test")
    for i, hop in enumerate(result.hop_log, start=1):
        assert hop.step == i

def test_cumulative_latency_increases():
    router, _ = get_router()
    result = router.route("Aethon", "Elos", "test")
    prev = 0.0
    for hop in result.hop_log:
        assert hop.cumulative_ms > prev
        prev = hop.cumulative_ms

def test_cumulative_equals_total():
    router, _ = get_router()
    result = router.route("Aethon", "Cyra", "Hello")
    if result.hop_log:
        assert abs(result.hop_log[-1].cumulative_ms - result.total_latency_ms) < 1e-6


# ──────────────────────────────────────────────────────────────────────────────
# Codec encoding in hop log
# ──────────────────────────────────────────────────────────────────────────────

def test_payload_encoded_in_dst_codex():
    """Each hop's payload must be encoded in the destination planet's codex."""
    router, u = get_router()
    msg = "Hello world"
    ascii_vals = [ord(c) for c in msg]
    result = router.route("Aethon", "Cyra", msg)
    assert not result.undeliverable

    for hop in result.hop_log:
        dst = u.get_planet(hop.dst_planet)
        expected = [_int_to_base(v, dst.codex) for v in ascii_vals]
        assert hop.payload_encoded == expected
        assert hop.payload_codex == dst.codex

def test_hello_world_first_hop_to_boros():
    """
    Aethon → Boros: Boros has codex=5.
    'H' (ASCII 72) in base 5 = '242' (per spec).
    """
    router, _ = get_router()
    result = router.route("Aethon", "Boros", "Hello world")
    assert not result.undeliverable
    hop = result.hop_log[0]
    assert hop.payload_codex == 5
    assert hop.payload_encoded[0] == "242"   # 'H' in base 5


# ──────────────────────────────────────────────────────────────────────────────
# Resilience — dead nodes
# ──────────────────────────────────────────────────────────────────────────────

def test_dead_origin_undeliverable():
    router, u = get_router()
    u.kill_node("Aethon")
    result = router.route("Aethon", "Cyra", "test")
    assert result.undeliverable

def test_dead_destination_undeliverable():
    router, u = get_router()
    u.kill_node("Cyra")
    result = router.route("Aethon", "Cyra", "test")
    assert result.undeliverable

def test_dead_intermediate_reroutes():
    """
    Kill a planet that was on the shortest path.
    Router must find an alternate route (not crash).
    """
    router, u = get_router()

    # First find the original shortest path
    original = router.route("Aethon", "Elos", "test")
    assert not original.undeliverable

    # Kill all intermediate planets on that path (keep origin & destination)
    for planet_id in original.path[1:-1]:
        u.kill_node(planet_id)

    # Re-route — should either find alternate or report undeliverable cleanly
    rerouted = router.route("Aethon", "Elos", "test")
    # Must not raise an exception — deliverable or not
    assert isinstance(rerouted.undeliverable, bool)

def test_restore_node_recovers_route():
    router, u = get_router()
    u.kill_node("Boros")
    u.restore_node("Boros")
    result = router.route("Aethon", "Boros", "test")
    assert not result.undeliverable


# ──────────────────────────────────────────────────────────────────────────────
# Resilience — dead links
# ──────────────────────────────────────────────────────────────────────────────

def test_dead_link_excluded_from_graph():
    router, u = get_router()
    # Kill direct Aethon↔Boros link
    u.kill_link("Aethon", "Boros")
    result = router.route("Aethon", "Boros", "test")
    # Either reroutes via another planet or is undeliverable — must not crash
    assert isinstance(result.undeliverable, bool)
    if not result.undeliverable:
        # Path must not use the dead link directly
        path = result.path
        for i in range(len(path) - 1):
            pair = {path[i], path[i+1]}
            assert pair != {"Aethon", "Boros"}

def test_restore_link_recovers_route():
    router, u = get_router()
    u.kill_link("Aethon", "Boros")
    u.restore_link("Aethon", "Boros")
    result = router.route("Aethon", "Boros", "test")
    assert not result.undeliverable


# ──────────────────────────────────────────────────────────────────────────────
# Undeliverable
# ──────────────────────────────────────────────────────────────────────────────

def test_unknown_planet_undeliverable():
    router, _ = get_router()
    result = router.route("Aethon", "Nonexistent", "test")
    assert result.undeliverable
    assert "Nonexistent" in result.undeliverable_reason

def test_undeliverable_has_reason():
    router, u = get_router()
    u.kill_node("Cyra")
    result = router.route("Aethon", "Cyra", "test")
    assert result.undeliverable
    assert len(result.undeliverable_reason) > 0


# ──────────────────────────────────────────────────────────────────────────────
# to_dict schema
# ──────────────────────────────────────────────────────────────────────────────

def test_to_dict_has_required_fields():
    router, _ = get_router()
    result = router.route("Aethon", "Boros", "Hi")
    d = result.to_dict()
    for key in ["origin_id", "destination_id", "message", "path",
                "hop_log", "total_latency_ms", "undeliverable", "hops"]:
        assert key in d

def test_hop_log_dict_has_required_fields():
    router, _ = get_router()
    result = router.route("Aethon", "Boros", "Hi")
    assert not result.undeliverable
    hop = result.to_dict()["hop_log"][0]
    for key in ["step", "src_planet", "dst_planet", "entry_tower",
                "send_tower", "recv_tower", "payload_encoded",
                "payload_codex", "latency_breakdown", "cumulative_ms"]:
        assert key in hop

def test_latency_breakdown_dict_complete():
    router, _ = get_router()
    result = router.route("Aethon", "Boros", "Hi")
    hop = result.to_dict()["hop_log"][0]
    bd = hop["latency_breakdown"]
    for key in ["fiber_ms", "atm_src_ms", "void_ms", "atm_dst_ms",
                "towers_ms", "total_ms", "towers_hit"]:
        assert key in bd


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
