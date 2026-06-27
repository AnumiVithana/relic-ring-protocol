"""
Routing Engine — finds the lowest-latency path across the star system.

Algorithm: Dijkstra's shortest path, edge weight = total hop latency (ms).

Key behaviours:
  - Builds the graph dynamically from the live Universe state each call,
    so dead nodes / severed links are automatically excluded.
  - Enforces Lmax: no edge is added if void distance exceeds the threshold.
  - Returns a RouteResult with the full hop_log, per-hop breakdowns,
    cumulative latency, and payload encoding at every stage.
  - If no path exists → RouteResult.undeliverable is True.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import UniverseConstants
from .latency import LatencyEngine, HopLatency
from .models import Planet, Tower, _int_to_base
from .universe import Universe


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HopEntry:
    """Single entry in the hop_log — one planet-to-planet transit."""
    step: int
    src_planet: str
    dst_planet: str

    # Tower indices (on their respective planets)
    entry_tower_idx: int        # tower where packet entered src via fiber / origin
    send_tower_idx: int         # tower on src that fires laser
    recv_tower_idx: int         # tower on dst that catches laser

    # Payload at this stage (encoded in dst planet's codex)
    payload_encoded: List[str]
    payload_codex: int

    # Latency breakdown for this hop
    latency: HopLatency

    # Cumulative latency up to and including this hop
    cumulative_ms: float

    def to_dict(self) -> dict:
        return {
            "step":              self.step,
            "src_planet":        self.src_planet,
            "dst_planet":        self.dst_planet,
            "entry_tower":       f"T_{self.entry_tower_idx}",
            "send_tower":        f"T_{self.send_tower_idx}",
            "recv_tower":        f"T_{self.recv_tower_idx}",
            "payload_encoded":   self.payload_encoded,
            "payload_codex":     self.payload_codex,
            "latency_breakdown": self.latency.breakdown(),
            "cumulative_ms":     round(self.cumulative_ms, 4),
        }


@dataclass
class RouteResult:
    """Complete result of a routing request."""
    origin_id: str
    destination_id: str
    message: str

    # Path as list of planet IDs  e.g. ["Aethon", "Boros", "Cyra"]
    path: List[str] = field(default_factory=list)

    # Ordered log of every hop taken
    hop_log: List[HopEntry] = field(default_factory=list)

    # Total end-to-end latency
    total_latency_ms: float = 0.0

    # True when no route exists
    undeliverable: bool = False
    undeliverable_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "origin_id":          self.origin_id,
            "destination_id":     self.destination_id,
            "message":            self.message,
            "path":               self.path,
            "hop_log":            [h.to_dict() for h in self.hop_log],
            "total_latency_ms":   round(self.total_latency_ms, 4),
            "undeliverable":      self.undeliverable,
            "undeliverable_reason": self.undeliverable_reason,
            "hops":               len(self.hop_log),
        }

    def pretty_print(self):
        if self.undeliverable:
            print(f"\n✗ UNDELIVERABLE: {self.undeliverable_reason}")
            return

        print(f"\n{'═'*60}")
        print(f"  ROUTE: {self.origin_id} → {' → '.join(self.path[1:])}")
        print(f"  HOPS : {len(self.hop_log)}")
        print(f"{'═'*60}")
        for h in self.hop_log:
            print(f"\n  Step {h.step}: {h.src_planet} → {h.dst_planet}")
            print(f"    towers : T_{h.entry_tower_idx}(entry) → "
                  f"T_{h.send_tower_idx}(send) ··· T_{h.recv_tower_idx}(recv)")
            print(f"    payload (base {h.payload_codex}): {h.payload_encoded}")
            print(f"    latency breakdown:")
            print(h.latency)
            print(f"    cumulative : {h.cumulative_ms:.4f} ms")
        print(f"\n{'─'*60}")
        print(f"  TOTAL LATENCY : {self.total_latency_ms:.4f} ms")
        print(f"{'═'*60}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────

class Router:
    """
    Shortest-latency router for the Relic Ring star system.

    Usage:
        router = Router(universe)
        result = router.route("Aethon", "Cyra", "Hello world")
        result.pretty_print()
    """

    def __init__(self, universe: Universe):
        self.universe = universe
        self.engine = LatencyEngine(universe.constants)

    # ── public API ────────────────────────────────────────────────────────────

    def route(self, origin_id: str, destination_id: str, message: str) -> RouteResult:
        """
        Route a message from origin to destination.
        Returns a RouteResult with full hop_log and latency breakdown.
        """
        result = RouteResult(
            origin_id=origin_id,
            destination_id=destination_id,
            message=message,
        )

        # Validate endpoints
        try:
            origin = self.universe.get_planet(origin_id)
            destination = self.universe.get_planet(destination_id)
        except KeyError as e:
            result.undeliverable = True
            result.undeliverable_reason = str(e)
            return result

        if not origin.active:
            result.undeliverable = True
            result.undeliverable_reason = f"Origin planet '{origin_id}' is dead."
            return result

        if not destination.active:
            result.undeliverable = True
            result.undeliverable_reason = f"Destination planet '{destination_id}' is dead."
            return result

        if origin_id == destination_id:
            result.path = [origin_id]
            result.total_latency_ms = 0.0
            return result

        # Find shortest path (planet IDs only)
        path, cost_ms = self._dijkstra(origin_id, destination_id)

        if path is None:
            result.undeliverable = True
            result.undeliverable_reason = (
                f"No valid route from '{origin_id}' to '{destination_id}'. "
                "All paths exceed Lmax or pass through dead nodes."
            )
            return result

        result.path = path
        result.total_latency_ms = cost_ms

        # Build detailed hop log with encoding
        result.hop_log = self._build_hop_log(path, message)

        return result

    # ── Dijkstra ──────────────────────────────────────────────────────────────

    def _dijkstra(
        self, origin_id: str, destination_id: str
    ) -> Tuple[Optional[List[str]], float]:
        """
        Standard Dijkstra on the planet graph.
        Edge weight = total hop latency in ms (using closest tower pair).
        Returns (path_list, total_ms) or (None, inf) if unreachable.
        """
        # dist[planet_id] = best known latency (ms) to reach it
        dist: Dict[str, float] = {pid: math.inf for pid in self.universe.planets}
        dist[origin_id] = 0.0
        prev: Dict[str, Optional[str]] = {pid: None for pid in self.universe.planets}

        # Min-heap: (latency_ms, planet_id)
        heap = [(0.0, origin_id)]

        visited = set()

        while heap:
            current_ms, current_id = heapq.heappop(heap)

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == destination_id:
                break

            current_planet = self.universe.get_planet(current_id)
            if not current_planet.active:
                continue

            # Explore neighbours
            for neighbour_id, neighbour in self.universe.planets.items():
                if neighbour_id == current_id:
                    continue
                if not neighbour.active:
                    continue
                if not self.universe.is_link_alive(current_id, neighbour_id):
                    continue
                if self.engine.exceeds_lmax(current_planet, neighbour):
                    continue

                edge_ms = self._hop_cost_ms(current_planet, neighbour)
                new_dist = current_ms + edge_ms

                if new_dist < dist[neighbour_id]:
                    dist[neighbour_id] = new_dist
                    prev[neighbour_id] = current_id
                    heapq.heappush(heap, (new_dist, neighbour_id))

        if dist[destination_id] == math.inf:
            return None, math.inf

        # Reconstruct path
        path = []
        node = destination_id
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()

        return path, dist[destination_id]

    def _hop_cost_ms(self, src: Planet, dst: Planet) -> float:
        """
        Cost of a direct hop: use closest tower pair, entry == send tower
        (Dijkstra only needs the weight; hop_log gets full detail separately).
        """
        send_t, recv_t = src.closest_tower_pair_to(dst)
        result = self.engine.compute(src, dst, send_t, send_t, recv_t)
        return result.total_ms

    # ── Hop log builder ───────────────────────────────────────────────────────

    def _build_hop_log(self, path: List[str], message: str) -> List[HopEntry]:
        """
        Walk the path and build a detailed HopEntry for every hop,
        including codec translations at each step.
        """
        ascii_vals = [ord(c) for c in message]
        hop_log: List[HopEntry] = []
        cumulative_ms = 0.0

        for step, (src_id, dst_id) in enumerate(zip(path, path[1:]), start=1):
            src = self.universe.get_planet(src_id)
            dst = self.universe.get_planet(dst_id)

            # Tower selection: closest pair for line-of-sight
            send_t, recv_t = src.closest_tower_pair_to(dst)

            # Entry tower:
            #   - Step 1: packet originates at send_t (no prior fiber leg)
            #   - Later steps: entry tower is the recv tower of the previous hop
            if step == 1:
                entry_t = send_t
            else:
                entry_t = Tower(
                    planet_id=src_id,
                    index=hop_log[-1].recv_tower_idx,
                    x_km=src.towers[hop_log[-1].recv_tower_idx].x_km,
                    y_km=src.towers[hop_log[-1].recv_tower_idx].y_km,
                )

            # Compute latency for this hop
            latency = self.engine.compute(src, dst, entry_t, send_t, recv_t)
            cumulative_ms += latency.total_ms

            # Encode payload into dst's codex for void transmission
            encoded = [_int_to_base(v, dst.codex) for v in ascii_vals]

            hop_log.append(HopEntry(
                step=step,
                src_planet=src_id,
                dst_planet=dst_id,
                entry_tower_idx=entry_t.index,
                send_tower_idx=send_t.index,
                recv_tower_idx=recv_t.index,
                payload_encoded=encoded,
                payload_codex=dst.codex,
                latency=latency,
                cumulative_ms=cumulative_ms,
            ))

        return hop_log
