"""
Pydantic schemas — request bodies and response models for the API.
All responses include a top-level 'ok' bool so the frontend
can check success without parsing HTTP status codes.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator


# ── Request bodies ────────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    origin_id: str
    destination_id: str
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty.")
        return v


class LinkRequest(BaseModel):
    planet_id_a: str
    planet_id_b: str


# ── Tower schema ──────────────────────────────────────────────────────────────

class TowerSchema(BaseModel):
    index: int
    x_km: float
    y_km: float


# ── Planet schema ─────────────────────────────────────────────────────────────

class PlanetSchema(BaseModel):
    id: str
    codex: int
    x_km: float
    y_km: float
    radius_km: float
    active_towers: int
    atmosphere_thickness_km: float
    refraction_index: float
    active: bool
    towers: List[TowerSchema]


# ── Universe schema ───────────────────────────────────────────────────────────

class UniverseSchema(BaseModel):
    planets: List[PlanetSchema]
    constants: Dict[str, Any]
    failed_nodes: List[str]
    failed_links: List[List[str]]


# ── Route response ────────────────────────────────────────────────────────────

class RouteResponse(BaseModel):
    ok: bool
    origin_id: str
    destination_id: str
    message: str
    path: List[str]
    hop_log: List[Dict[str, Any]]
    total_latency_ms: float
    hops: int
    undeliverable: bool
    undeliverable_reason: str


# ── Chaos response ────────────────────────────────────────────────────────────

class ChaosResponse(BaseModel):
    ok: bool
    action: str
    detail: str
    failed_nodes: List[str]
    failed_links: List[List[str]]


# ── Status response ───────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    total_planets: int
    active_planets: int
    dead_planets: int
    failed_nodes: List[str]
    failed_links: List[List[str]]
