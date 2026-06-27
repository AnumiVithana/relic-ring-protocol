"""

Packet schema (per spec section 7) and route hop
records used to build hop_log and the latency breakdown.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HopLogEntry:
    """One entry in a packet's hop_log -- proves the route taken."""
    planet_id: str
    tower_index: int
    event: str  
    payload_snapshot: str 
    codex_base: int
    t_p_ms: float = 0.0
    t_v_ms: float = 0.0
    note: str = ""


@dataclass
class Packet:
    origin_id: str
    destination_id: str
    current_id: str
    payload: str  
    hop_log: list = field(default_factory=list)

    
    original_payload: str = ""
    total_latency_ms: float = 0.0
    delivered: bool = False
    undeliverable_reason: str | None = None

    def __post_init__(self):
        if not self.original_payload:
            self.original_payload = self.payload


@dataclass
class RouteEdge:
    """One leg of a planet-level route, with its latency breakdown."""
    from_planet: str
    to_planet: str
    from_tower: int
    to_tower: int
    t_v_ms: float
    void_distance_km: float


@dataclass
class PlannedRoute:
    planet_path: list
    edges: list
    total_latency_ms: float
    breakdown: dict
