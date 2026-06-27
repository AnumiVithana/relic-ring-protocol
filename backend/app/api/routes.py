"""
API Route Handlers

All routes pull the Universe singleton from app.state so every
request shares the same live state (failures persist across calls).
"""

from fastapi import APIRouter, Request, HTTPException

from ..core.router import Router
from ..core.universe import Universe
from .schemas import (
    RouteRequest, RouteResponse,
    LinkRequest, ChaosResponse,
    UniverseSchema, PlanetSchema, TowerSchema,
    StatusResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_universe(request: Request) -> Universe:
    return request.app.state.universe


def _failed_links_serializable(universe: Universe) -> list:
    """Convert frozenset links to sorted lists for JSON serialisation."""
    return [sorted(list(link)) for link in universe._failed_links]


def _planet_schema(planet) -> PlanetSchema:
    return PlanetSchema(
        id=planet.id,
        codex=planet.codex,
        x_km=planet.x_km,
        y_km=planet.y_km,
        radius_km=planet.radius_km,
        active_towers=planet.active_towers,
        atmosphere_thickness_km=planet.atmosphere_thickness_km,
        refraction_index=planet.refraction_index,
        active=planet.active,
        towers=[
            TowerSchema(index=t.index, x_km=t.x_km, y_km=t.y_km)
            for t in planet.towers
        ],
    )


# ── Universe state ────────────────────────────────────────────────────────────

@router.get(
    "/universe",
    response_model=UniverseSchema,
    tags=["Universe"],
    summary="Get full universe state including all planets, towers, and constants.",
)
def get_universe_state(request: Request):
    u = get_universe(request)
    c = u.constants
    return UniverseSchema(
        planets=[_planet_schema(p) for p in u.all_planets()],
        constants={
            "speed_of_light_km_s":      c.speed_of_light_km_s,
            "fiber_speed_km_s":         c.fiber_speed_km_s,
            "fiber_speed_fraction":     c.fiber_speed_fraction,
            "tower_delay_ms":           c.tower_delay_ms,
            "lmax_km":                  c.lmax_km,
            "coordinate_scale_unit_km": c.coordinate_scale_unit_km,
        },
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )


@router.get(
    "/universe/planet/{planet_id}",
    response_model=PlanetSchema,
    tags=["Universe"],
    summary="Get a single planet by ID.",
)
def get_planet(planet_id: str, request: Request):
    u = get_universe(request)
    try:
        planet = u.get_planet(planet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Planet '{planet_id}' not found.")
    return _planet_schema(planet)


# ── Routing ───────────────────────────────────────────────────────────────────

@router.post(
    "/route",
    response_model=RouteResponse,
    tags=["Routing"],
    summary="Route a message between two planets.",
)
def route_message(body: RouteRequest, request: Request):
    u = get_universe(request)
    router_engine = Router(u)
    result = router_engine.route(body.origin_id, body.destination_id, body.message)
    d = result.to_dict()
    return RouteResponse(
        ok=not result.undeliverable,
        origin_id=d["origin_id"],
        destination_id=d["destination_id"],
        message=d["message"],
        path=d["path"],
        hop_log=d["hop_log"],
        total_latency_ms=d["total_latency_ms"],
        hops=d["hops"],
        undeliverable=d["undeliverable"],
        undeliverable_reason=d["undeliverable_reason"],
    )


# ── Chaos — node failures ─────────────────────────────────────────────────────

@router.post(
    "/chaos/kill-node/{planet_id}",
    response_model=ChaosResponse,
    tags=["Chaos"],
    summary="Kill a planet node — simulates hardware failure.",
)
def kill_node(planet_id: str, request: Request):
    u = get_universe(request)
    try:
        u.kill_node(planet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Planet '{planet_id}' not found.")
    return ChaosResponse(
        ok=True,
        action="kill_node",
        detail=f"Node '{planet_id}' is now DEAD.",
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )


@router.post(
    "/chaos/restore-node/{planet_id}",
    response_model=ChaosResponse,
    tags=["Chaos"],
    summary="Restore a dead planet node.",
)
def restore_node(planet_id: str, request: Request):
    u = get_universe(request)
    try:
        u.restore_node(planet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Planet '{planet_id}' not found.")
    return ChaosResponse(
        ok=True,
        action="restore_node",
        detail=f"Node '{planet_id}' is now ACTIVE.",
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )


# ── Chaos — link failures ─────────────────────────────────────────────────────

@router.post(
    "/chaos/kill-link",
    response_model=ChaosResponse,
    tags=["Chaos"],
    summary="Sever the direct link between two planets.",
)
def kill_link(body: LinkRequest, request: Request):
    u = get_universe(request)
    for pid in [body.planet_id_a, body.planet_id_b]:
        try:
            u.get_planet(pid)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Planet '{pid}' not found.")
    u.kill_link(body.planet_id_a, body.planet_id_b)
    return ChaosResponse(
        ok=True,
        action="kill_link",
        detail=f"Link '{body.planet_id_a}' ↔ '{body.planet_id_b}' severed.",
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )


@router.post(
    "/chaos/restore-link",
    response_model=ChaosResponse,
    tags=["Chaos"],
    summary="Restore a severed link between two planets.",
)
def restore_link(body: LinkRequest, request: Request):
    u = get_universe(request)
    u.restore_link(body.planet_id_a, body.planet_id_b)
    return ChaosResponse(
        ok=True,
        action="restore_link",
        detail=f"Link '{body.planet_id_a}' ↔ '{body.planet_id_b}' restored.",
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )


# ── Status ────────────────────────────────────────────────────────────────────

@router.get(
    "/chaos/status",
    response_model=StatusResponse,
    tags=["Chaos"],
    summary="Current failure state of the network.",
)
def chaos_status(request: Request):
    u = get_universe(request)
    total = len(u.planets)
    active = len(u.active_planets())
    return StatusResponse(
        total_planets=total,
        active_planets=active,
        dead_planets=total - active,
        failed_nodes=list(u._failed_nodes),
        failed_links=_failed_links_serializable(u),
    )
