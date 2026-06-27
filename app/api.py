"""
FastAPI application exposing the Relic Ring Protocol simulation.

Endpoints
  GET  /api/universe                 -> full universe state (planets, towers, edges, failures)
  POST /api/send                     -> send a packet, get full hop_log + breakdown
  POST /api/chaos/kill-node          -> simulate a node failure
  POST /api/chaos/revive-node        -> bring a node back online
  POST /api/chaos/kill-link          -> simulate a link failure
  POST /api/chaos/revive-link        -> bring a link back online
  WS   /ws                            -> live packet animation events (for the frontend canvas)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import UniverseConfig
from app.geometry import all_tower_positions
from app.network import send_packet
from app.universe import UniverseGraph

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "universe-config.json"

app = FastAPI(title="Relic Ring Protocol")

_config: UniverseConfig = UniverseConfig.load(CONFIG_PATH)
_graph: UniverseGraph = UniverseGraph.build(_config)

_ws_clients: list[WebSocket] = []


class SendRequest(BaseModel):
    origin: str
    destination: str
    message: str


class NodeChaosRequest(BaseModel):
    planet_id: str


class LinkChaosRequest(BaseModel):
    planet_a: str
    planet_b: str


def _planet_public_state(planet_id: str) -> dict:
    planet = _config.planets[planet_id]
    towers = all_tower_positions(planet, _config.metadata.coordinate_scale_unit_km)
    return {
        "id": planet.id,
        "codex": planet.codex,
        "x": planet.x,
        "y": planet.y,
        "radius_km": planet.radius_km,
        "active_towers": planet.active_towers,
        "atmosphere_thickness_km": planet.atmosphere_thickness_km,
        "refraction_index": planet.refraction_index,
        "alive": _graph.is_planet_alive(planet.id),
        "towers": [
            {"index": t.index, "angle_deg": t.angle_deg, "x_km": t.x_km, "y_km": t.y_km}
            for t in towers
        ],
    }


@app.get("/api/universe")
def get_universe():
    meta = _config.metadata
    edges = []
    for pair, info in _graph.void_edges.items():
        a, b = sorted(pair)
        edges.append({
            "planet_a": a,
            "planet_b": b,
            "blocked_by_lmax": info is None,
            "L_km": info.L_km if info else None,
            "t_v_ms": (info.t_v_s * 1000.0) if info else None,
            "tower_a": info.tower_a if info else None,
            "tower_b": info.tower_b if info else None,
            "alive": _graph.is_link_alive(a, b),
        })

    return {
        "metadata": {
            "system_name": meta.system_name,
            "speed_of_light_kms": meta.speed_of_light_kms,
            "max_void_hop_distance_km": meta.max_void_hop_distance_km,
            "coordinate_scale_unit_km": meta.coordinate_scale_unit_km,
            "tower_processing_delay_ms": meta.tower_processing_delay_ms,
            "fiber_speed_fraction": meta.fiber_speed_fraction,
        },
        "planets": [_planet_public_state(pid) for pid in _config.planets],
        "edges": edges,
        "failed_nodes": list(_graph.failed_nodes),
        "failed_links": [sorted(list(fs)) for fs in _graph.failed_links],
    }


@app.post("/api/send")
async def post_send(req: SendRequest):
    if req.origin not in _config.planets:
        return {"delivered": False, "reason": f"Unknown origin planet '{req.origin}'."}
    if req.destination not in _config.planets:
        return {"delivered": False, "reason": f"Unknown destination planet '{req.destination}'."}

    result = send_packet(_config, _graph, req.origin, req.destination, req.message)

    payload = {
        "delivered": result.delivered,
        "reason": result.reason,
        "planet_path": result.planet_path,
        "final_payload": result.packet.payload if result.delivered else None,
        "total_latency_ms": result.breakdown.total_ms,
        "breakdown": {
            "fiber_ms": result.breakdown.fiber_ms,
            "tower_processing_ms": result.breakdown.tower_processing_ms,
            "atmosphere_and_void_ms": result.breakdown.atmosphere_and_void_ms,
            "total_ms": result.breakdown.total_ms,
        },
        "hop_log": [
            {
                "planet_id": h.planet_id,
                "tower_index": h.tower_index,
                "event": h.event,
                "payload_snapshot": h.payload_snapshot,
                "codex_base": h.codex_base,
                "t_p_ms": h.t_p_ms,
                "t_v_ms": h.t_v_ms,
                "note": h.note,
            }
            for h in result.packet.hop_log
        ],
    }

    await _broadcast({"type": "packet_sent", "data": payload})
    return payload


@app.post("/api/chaos/kill-node")
async def kill_node(req: NodeChaosRequest):
    if req.planet_id not in _config.planets:
        return {"ok": False, "reason": "Unknown planet."}
    _graph.kill_planet(req.planet_id)
    await _broadcast({"type": "node_killed", "data": {"planet_id": req.planet_id}})
    return {"ok": True}


@app.post("/api/chaos/revive-node")
async def revive_node(req: NodeChaosRequest):
    _graph.revive_planet(req.planet_id)
    await _broadcast({"type": "node_revived", "data": {"planet_id": req.planet_id}})
    return {"ok": True}


@app.post("/api/chaos/kill-link")
async def kill_link(req: LinkChaosRequest):
    _graph.kill_link(req.planet_a, req.planet_b)
    await _broadcast({"type": "link_killed", "data": {"planet_a": req.planet_a, "planet_b": req.planet_b}})
    return {"ok": True}


@app.post("/api/chaos/revive-link")
async def revive_link(req: LinkChaosRequest):
    _graph.revive_link(req.planet_a, req.planet_b)
    await _broadcast({"type": "link_revived", "data": {"planet_a": req.planet_a, "planet_b": req.planet_b}})
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def _broadcast(message: dict):
    dead = []
    for client in _ws_clients:
        try:
            await client.send_json(message)
        except Exception:
            dead.append(client)
    for d in dead:
        if d in _ws_clients:
            _ws_clients.remove(d)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))
