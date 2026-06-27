"""
API integration tests — spins up the full FastAPI app in-process.
No server needed: uses httpx TestClient.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "online"
    assert data["planets"] == 5


# ── Universe ──────────────────────────────────────────────────────────────────

def test_get_universe():
    r = client.get("/universe")
    assert r.status_code == 200
    data = r.json()
    assert len(data["planets"]) == 5
    assert "constants" in data
    assert "failed_nodes" in data

def test_get_universe_planet_fields():
    r = client.get("/universe")
    planet = r.json()["planets"][0]
    for field in ["id", "codex", "x_km", "y_km", "radius_km",
                  "active_towers", "atmosphere_thickness_km",
                  "refraction_index", "active", "towers"]:
        assert field in planet

def test_get_universe_tower_fields():
    r = client.get("/universe")
    tower = r.json()["planets"][0]["towers"][0]
    for field in ["index", "x_km", "y_km"]:
        assert field in tower

def test_get_single_planet():
    r = client.get("/universe/planet/Aethon")
    assert r.status_code == 200
    assert r.json()["id"] == "Aethon"

def test_get_unknown_planet_404():
    r = client.get("/universe/planet/Nonexistent")
    assert r.status_code == 404


# ── Routing ───────────────────────────────────────────────────────────────────

def test_route_basic():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "Hello world"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["path"][0] == "Aethon"
    assert data["path"][-1] == "Boros"
    assert data["total_latency_ms"] > 0
    assert data["hops"] >= 1

def test_route_response_fields():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "test"
    })
    data = r.json()
    for field in ["ok", "origin_id", "destination_id", "message",
                  "path", "hop_log", "total_latency_ms", "hops",
                  "undeliverable", "undeliverable_reason"]:
        assert field in data

def test_route_hop_log_fields():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "test"
    })
    hop = r.json()["hop_log"][0]
    for field in ["step", "src_planet", "dst_planet", "entry_tower",
                  "send_tower", "recv_tower", "payload_encoded",
                  "payload_codex", "latency_breakdown", "cumulative_ms"]:
        assert field in hop

def test_route_latency_breakdown_fields():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "test"
    })
    bd = r.json()["hop_log"][0]["latency_breakdown"]
    for field in ["fiber_ms", "atm_src_ms", "void_ms",
                  "atm_dst_ms", "towers_ms", "total_ms", "towers_hit"]:
        assert field in bd

def test_route_same_planet():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Aethon",
        "message": "ping"
    })
    data = r.json()
    assert data["ok"] is True
    assert data["total_latency_ms"] == 0.0
    assert data["hops"] == 0

def test_route_empty_message_rejected():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": ""
    })
    assert r.status_code == 422

def test_route_unknown_planet():
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Ghost",
        "message": "test"
    })
    data = r.json()
    assert data["ok"] is False
    assert data["undeliverable"] is True


# ── Chaos — nodes ─────────────────────────────────────────────────────────────

def test_kill_and_restore_node():
    # Kill Boros
    r = client.post("/chaos/kill-node/Boros")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "Boros" in data["failed_nodes"]

    # Universe should reflect it
    u = client.get("/universe").json()
    boros = next(p for p in u["planets"] if p["id"] == "Boros")
    assert boros["active"] is False

    # Routing to Boros should fail
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "test"
    })
    assert r.json()["undeliverable"] is True

    # Restore
    r = client.post("/chaos/restore-node/Boros")
    assert r.status_code == 200
    assert "Boros" not in r.json()["failed_nodes"]

    # Should route again
    r = client.post("/route", json={
        "origin_id": "Aethon",
        "destination_id": "Boros",
        "message": "test"
    })
    assert r.json()["ok"] is True

def test_kill_unknown_node_404():
    r = client.post("/chaos/kill-node/GhostPlanet")
    assert r.status_code == 404


# ── Chaos — links ─────────────────────────────────────────────────────────────

def test_kill_and_restore_link():
    r = client.post("/chaos/kill-link", json={
        "planet_id_a": "Aethon",
        "planet_id_b": "Boros"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert ["Aethon", "Boros"] in data["failed_links"] or \
           ["Boros", "Aethon"] in data["failed_links"]

    # Restore
    r = client.post("/chaos/restore-link", json={
        "planet_id_a": "Aethon",
        "planet_id_b": "Boros"
    })
    assert r.status_code == 200
    assert data["ok"] is True

def test_kill_link_unknown_planet_404():
    r = client.post("/chaos/kill-link", json={
        "planet_id_a": "Aethon",
        "planet_id_b": "Ghost"
    })
    assert r.status_code == 404


# ── Chaos status ──────────────────────────────────────────────────────────────

def test_chaos_status():
    r = client.get("/chaos/status")
    assert r.status_code == 200
    data = r.json()
    for field in ["total_planets", "active_planets", "dead_planets",
                  "failed_nodes", "failed_links"]:
        assert field in data
    assert data["total_planets"] == 5
    assert data["active_planets"] + data["dead_planets"] == data["total_planets"]
