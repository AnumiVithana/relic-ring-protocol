"""

Shortest-latency pathfinding over the tower-level UniverseGraph.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from app.universe import UniverseGraph


@dataclass
class TowerPathResult:
    found: bool
    tower_path: list = field(default_factory=list)
    total_latency_s: float = 0.0
    reason: str = ""


def dijkstra_towers(graph: UniverseGraph, start_node, goal_planet_id: str) -> TowerPathResult:
    """
    Runs Dijkstra from a specific starting tower-node to ANY tower on the
    goal planet (the destination tower is determined by line-of-sight from
    whichever planet routes there, not chosen in advance).
    """
    dist = {start_node: 0.0}
    prev = {}
    visited = set()
    pq = [(0.0, start_node)]

    while pq:
        d, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)

        if node[0] == goal_planet_id:
            path = _reconstruct_path(prev, start_node, node)
            return TowerPathResult(found=True, tower_path=path, total_latency_s=d)

        for neighbor, weight_s, _kind, _meta in graph.neighbors(node):
            if neighbor in visited:
                continue
            nd = d + weight_s
            if nd < dist.get(neighbor, float("inf")):
                dist[neighbor] = nd
                prev[neighbor] = node
                heapq.heappush(pq, (nd, neighbor))

    return TowerPathResult(
        found=False, total_latency_s=float("inf"),
        reason="No route exists between origin and destination "
               "(graph disconnected -- check for failed nodes/links or an "
               "unbridged Lmax gap).",
    )


def _reconstruct_path(prev: dict, start_node, goal_node) -> list:
    path = [goal_node]
    node = goal_node
    while node != start_node:
        node = prev[node]
        path.append(node)
    path.reverse()
    return path


def find_best_route(
    graph: UniverseGraph, origin_id: str, destination_id: str
) -> TowerPathResult:
    """
    Tries every tower on the origin planet as a starting point (the packet
    is generated planet-side, not at a pre-chosen tower) and returns the
    globally best (lowest total latency) result, with the origin's first
    tower-processing delay added on top.
    """
    if origin_id == destination_id:
        return TowerPathResult(
            found=False, reason="Origin and destination are the same planet."
        )

    if not graph.is_planet_alive(origin_id):
        return TowerPathResult(
            found=False, reason=f"Origin planet '{origin_id}' is currently offline."
        )
    if not graph.is_planet_alive(destination_id):
        return TowerPathResult(
            found=False, reason=f"Destination planet '{destination_id}' is currently offline."
        )

    origin_planet = graph.config.planets[origin_id]
    dt_s = graph.config.metadata.tower_processing_delay_ms / 1000.0

    best: TowerPathResult | None = None
    for tower_idx in range(origin_planet.active_towers):
        start_node = (origin_id, tower_idx)
        result = dijkstra_towers(graph, start_node, destination_id)
        if result.found:
            adjusted_latency = result.total_latency_s + dt_s
            candidate = TowerPathResult(
                found=True, tower_path=result.tower_path, total_latency_s=adjusted_latency
            )
            if best is None or candidate.total_latency_s < best.total_latency_s:
                best = candidate

    if best is None:
        return TowerPathResult(
            found=False,
            reason="No deliverable route found: destination is unreachable "
                   "given current topology, Lmax constraints, and any "
                   "failed nodes/links.",
        )
    return best


def planet_path_from_tower_path(tower_path: list) -> list:
    """Collapse a tower-level path into the sequence of distinct planets visited."""
    planets = []
    for planet_id, _tower_idx in tower_path:
        if not planets or planets[-1] != planet_id:
            planets.append(planet_id)
    return planets
