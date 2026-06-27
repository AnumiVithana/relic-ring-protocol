"""

Builds a TOWER-LEVEL graph from the parsed config. This is the key
architectural decision for this implementation:

  Graph nodes  = individual towers (planet_id, tower_index)
  Graph edges  = two kinds:
    (a) INTRA-PLANET edges: every tower on a planet connects to every other
        tower on the same planet, weighted by the fiber-arc transit time
        between them (T_p's arc term) PLUS one tower's processing delay
        (the exit tower's). Combined with charging the entry tower's delay
        on the inbound void edge (see below), this correctly reproduces
        "m=1 if entry==exit tower" (no intra-planet edge traversed, only
        one delay paid) and "m=2 otherwise" (exactly two delays paid total
        across the inbound void edge + the intra-planet edge).
    (b) INTER-PLANET (void) edges: only between the LINE-OF-SIGHT closest
        tower pair for each pair of planets whose void distance L does not
        exceed max_void_hop_distance_km. Hops longer than Lmax are simply
        not added as edges, forcing the shortest-path search to route
        through an intermediate planet (or report undeliverable if none
        exists).

A single, standard Dijkstra run over tower-nodes then produces a path that
already encodes the correct entry/exit tower at every intermediate planet.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import UniverseConfig
from app.geometry import angular_separation_deg, closest_tower_pair
from app.latency import crust_transit_time_s, void_distance_km, void_travel_time_s


@dataclass
class VoidEdgeInfo:
    planet_a: str
    tower_a: int
    planet_b: str
    tower_b: int
    L_km: float
    t_v_s: float


@dataclass
class UniverseGraph:
    config: UniverseConfig
    adjacency: dict = field(default_factory=dict)
    void_edges: dict = field(default_factory=dict)
    failed_nodes: set = field(default_factory=set)
    failed_links: set = field(default_factory=set)

    @classmethod
    def build(cls, config: UniverseConfig) -> "UniverseGraph":
        meta = config.metadata
        adjacency: dict = {}
        void_edges: dict = {}
        dt_s = meta.tower_processing_delay_ms / 1000.0

       
        for planet in config.planets.values():
            n = planet.active_towers
            for i in range(n):
                adjacency.setdefault((planet.id, i), [])
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    angle_i = (360.0 / n) * i
                    angle_j = (360.0 / n) * j
                    s = angular_separation_deg(angle_i, angle_j)
                    t_p_s = crust_transit_time_s(
                        planet,
                        angular_separation_deg=s,
                        same_tower=False,
                        fiber_speed_fraction=meta.fiber_speed_fraction,
                        speed_of_light_kms=meta.speed_of_light_kms,
                        tower_processing_delay_ms=meta.tower_processing_delay_ms,
                    )
                    
                    edge_weight_s = t_p_s - dt_s
                    node_i, node_j = (planet.id, i), (planet.id, j)
                    adjacency[node_i].append(
                        (node_j, edge_weight_s, "intra", {"planet": planet.id, "s_deg": s})
                    )

        
        planet_ids = list(config.planets.keys())
        for a_idx in range(len(planet_ids)):
            for b_idx in range(a_idx + 1, len(planet_ids)):
                pa = config.planets[planet_ids[a_idx]]
                pb = config.planets[planet_ids[b_idx]]

                L = void_distance_km(pa, pb, meta.coordinate_scale_unit_km)
                key = frozenset({pa.id, pb.id})

                if L > meta.max_void_hop_distance_km:
                    void_edges[key] = None  
                    continue

                tower_a, tower_b, _los_dist = closest_tower_pair(
                    pa, pb, meta.coordinate_scale_unit_km
                )
                t_v_s = void_travel_time_s(pa, pb, L, meta.speed_of_light_kms)

                void_edges[key] = VoidEdgeInfo(
                    planet_a=pa.id, tower_a=tower_a.index,
                    planet_b=pb.id, tower_b=tower_b.index,
                    L_km=L, t_v_s=t_v_s,
                )

                node_a = (pa.id, tower_a.index)
                node_b = (pb.id, tower_b.index)
                adjacency.setdefault(node_a, [])
                adjacency.setdefault(node_b, [])
                
                adjacency[node_a].append((node_b, t_v_s + dt_s, "void", {"L_km": L}))
                adjacency[node_b].append((node_a, t_v_s + dt_s, "void", {"L_km": L}))

        return cls(config=config, adjacency=adjacency, void_edges=void_edges)

    
    def kill_planet(self, planet_id: str) -> None:
        self.failed_nodes.add(planet_id)

    def revive_planet(self, planet_id: str) -> None:
        self.failed_nodes.discard(planet_id)

    def kill_link(self, planet_a: str, planet_b: str) -> None:
        self.failed_links.add(frozenset({planet_a, planet_b}))

    def revive_link(self, planet_a: str, planet_b: str) -> None:
        self.failed_links.discard(frozenset({planet_a, planet_b}))

    def is_link_alive(self, planet_a: str, planet_b: str) -> bool:
        return frozenset({planet_a, planet_b}) not in self.failed_links

    def is_planet_alive(self, planet_id: str) -> bool:
        return planet_id not in self.failed_nodes

    def neighbors(self, node):
        """
        Yields (neighbor_node, weight_seconds, kind, meta) for a tower node,
        respecting currently-failed planets/links (used for live rerouting).
        """
        planet_id, _tower_idx = node
        if not self.is_planet_alive(planet_id):
            return
        for neighbor_node, weight_s, kind, meta in self.adjacency.get(node, []):
            neighbor_planet = neighbor_node[0]
            if not self.is_planet_alive(neighbor_planet):
                continue
            if kind == "void" and not self.is_link_alive(planet_id, neighbor_planet):
                continue
            yield neighbor_node, weight_s, kind, meta
