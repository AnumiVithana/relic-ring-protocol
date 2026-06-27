
from __future__ import annotations

from dataclasses import dataclass, field

from app.codex import ascii_bytes, bytes_to_ascii_text, decode_from_codex, encode_to_codex
from app.config import UniverseConfig
from app.geometry import angular_separation_deg
from app.latency import crust_transit_time_s, seconds_to_ms
from app.models import HopLogEntry, Packet
from app.routing import find_best_route, planet_path_from_tower_path
from app.universe import UniverseGraph


@dataclass
class LatencyBreakdown:
    fiber_ms: float = 0.0
    tower_processing_ms: float = 0.0
    atmosphere_and_void_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class TransmissionResult:
    packet: Packet
    delivered: bool
    planet_path: list = field(default_factory=list)
    breakdown: LatencyBreakdown = field(default_factory=LatencyBreakdown)
    reason: str = ""


def send_packet(
    config: UniverseConfig, graph: UniverseGraph, origin_id: str, destination_id: str, message: str
) -> TransmissionResult:
    packet = Packet(
        origin_id=origin_id, destination_id=destination_id,
        current_id=origin_id, payload=message,
    )

    route = find_best_route(graph, origin_id, destination_id)
    if not route.found:
        packet.delivered = False
        packet.undeliverable_reason = route.reason
        return TransmissionResult(
            packet=packet, delivered=False, reason=route.reason,
        )

    tower_path = route.tower_path
    planet_path = planet_path_from_tower_path(tower_path)
    meta = config.metadata
    dt_ms = meta.tower_processing_delay_ms

    breakdown = LatencyBreakdown()
    byte_values = ascii_bytes(message)

    visits = _group_into_planet_visits(tower_path)

    current_bytes = byte_values
    for visit_idx, visit in enumerate(visits):
        planet = config.planets[visit["planet_id"]]
        is_origin = visit_idx == 0
        is_destination = visit_idx == len(visits) - 1
        entry_tower = visit["entry_tower"]
        exit_tower = visit["exit_tower"]

        same_tower = (entry_tower == exit_tower) or is_origin or is_destination
        s_deg = 0.0
        if not is_origin and not is_destination and entry_tower != exit_tower:
            angle_entry = (360.0 / planet.active_towers) * entry_tower
            angle_exit = (360.0 / planet.active_towers) * exit_tower
            s_deg = angular_separation_deg(angle_entry, angle_exit)

        t_p_s = crust_transit_time_s(
            planet, s_deg, same_tower,
            meta.fiber_speed_fraction, meta.speed_of_light_kms, meta.tower_processing_delay_ms,
        )
        t_p_ms = seconds_to_ms(t_p_s)
        if same_tower:
            tower_hits = 1
        else:
            s_seg = round(s_deg / (360.0 / planet.active_towers))
            tower_hits = s_seg + 1
        arc_ms = t_p_ms - (tower_hits * dt_ms)

        breakdown.fiber_ms += arc_ms
        breakdown.tower_processing_ms += tower_hits * dt_ms

        if not is_origin:
            current_bytes = decode_from_codex(
                [str(t) for t in visit["incoming_tokens"]], visit["incoming_codex"]
            )
            packet.hop_log.append(HopLogEntry(
                planet_id=planet.id, tower_index=entry_tower, event="relay_in",
                payload_snapshot=bytes_to_ascii_text(current_bytes),
                codex_base=10,
                t_p_ms=0.0, t_v_ms=0.0,  
                note=f"Decoded from Base-{visit['incoming_codex']} back to ASCII for internal routing.",
            ))

        if is_destination:
            packet.payload = bytes_to_ascii_text(current_bytes)
            packet.current_id = planet.id
            packet.delivered = True
            packet.hop_log.append(HopLogEntry(
                planet_id=planet.id, tower_index=entry_tower, event="destination",
                payload_snapshot=packet.payload, codex_base=planet.codex,
                t_p_ms=dt_ms, t_v_ms=0.0,
                note="Final decoding complete. Payload delivered.",
            ))
            continue

        next_planet_id = visits[visit_idx + 1]["planet_id"]
        next_codex = config.planets[next_planet_id].codex
        outgoing_tokens = encode_to_codex(current_bytes, next_codex)

        event = "origin" if is_origin else "relay_out"
        
        leg_cost_ms = dt_ms if is_origin else (arc_ms + dt_ms)
        packet.hop_log.append(HopLogEntry(
            planet_id=planet.id, tower_index=exit_tower, event=event,
            payload_snapshot=" ".join(outgoing_tokens), codex_base=next_codex,
            t_p_ms=leg_cost_ms,
            t_v_ms=0.0,
            note=f"Encoded ASCII -> Base-{next_codex} for transmission to {next_planet_id}.",
        ))

        if visit_idx + 1 < len(visits):
            visits[visit_idx + 1]["incoming_tokens"] = outgoing_tokens
            visits[visit_idx + 1]["incoming_codex"] = next_codex

        pair_key = frozenset({planet.id, next_planet_id})
        void_info = graph.void_edges.get(pair_key)
        if void_info is not None:
            t_v_ms = seconds_to_ms(void_info.t_v_s)
            breakdown.atmosphere_and_void_ms += t_v_ms
            packet.hop_log.append(HopLogEntry(
                planet_id=planet.id, tower_index=exit_tower, event="void_transit",
                payload_snapshot=" ".join(outgoing_tokens), codex_base=next_codex,
                t_p_ms=0.0, t_v_ms=t_v_ms,
                note=f"Laser transmission across the void to {next_planet_id} "
                     f"(L={void_info.L_km:,.0f} km).",
            ))

    breakdown.total_ms = (
        breakdown.fiber_ms + breakdown.tower_processing_ms + breakdown.atmosphere_and_void_ms
    )
    packet.total_latency_ms = breakdown.total_ms

    return TransmissionResult(
        packet=packet, delivered=True, planet_path=planet_path, breakdown=breakdown,
    )


def _group_into_planet_visits(tower_path: list) -> list:
    """
    Collapses a tower-level path like
        [(A,1), (A,3), (B,0), (B,5), (C,2)]
    into per-planet visit records.
    """
    visits = []
    i = 0
    n = len(tower_path)
    while i < n:
        planet_id, tower_idx = tower_path[i]
        entry_tower = tower_idx
        exit_tower = tower_idx
        j = i
        while j + 1 < n and tower_path[j + 1][0] == planet_id:
            j += 1
            exit_tower = tower_path[j][1]
        visits.append({
            "planet_id": planet_id,
            "entry_tower": entry_tower,
            "exit_tower": exit_tower,
            "incoming_tokens": None,
            "incoming_codex": None,
        })
        i = j + 1
    return visits
