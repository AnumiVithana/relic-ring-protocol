import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import UniverseConfig
from app.network import send_packet
from app.routing import find_best_route, planet_path_from_tower_path
from app.universe import UniverseGraph

CONFIG_PATH = Path(__file__).resolve().parents[1] / "universe-config.json"


def load_graph():
    cfg = UniverseConfig.load(CONFIG_PATH)
    return cfg, UniverseGraph.build(cfg)


def test_lmax_blocks_direct_aegis_caelum():
    cfg, graph = load_graph()
    key = frozenset({"Aegis", "Caelum"})
    assert graph.void_edges[key] is None


def test_aegis_to_caelum_routes_through_intermediate():
    cfg, graph = load_graph()
    result = find_best_route(graph, "Aegis", "Caelum")
    assert result.found
    path = planet_path_from_tower_path(result.tower_path)
    assert path[0] == "Aegis" and path[-1] == "Caelum"
    assert len(path) > 2


def test_payload_survives_multi_hop_round_trip():
    cfg, graph = load_graph()
    result = send_packet(cfg, graph, "Aegis", "Caelum", "Hello world")
    assert result.delivered
    assert result.packet.payload == "Hello world"


def test_dynamic_rerouting_around_dead_node():
    cfg, graph = load_graph()
    graph.kill_planet("Dawn")
    rerouted = find_best_route(graph, "Aegis", "Caelum")
    assert rerouted.found
    new_path = planet_path_from_tower_path(rerouted.tower_path)
    assert "Dawn" not in new_path


def test_full_isolation_is_undeliverable():
    cfg, graph = load_graph()
    for neighbor in ("Dawn", "Elysium", "Fenix"):
        graph.kill_planet(neighbor)
    result = send_packet(cfg, graph, "Aegis", "Caelum", "test")
    assert not result.delivered


def test_revive_restores_route():
    cfg, graph = load_graph()
    graph.kill_planet("Dawn")
    graph.revive_planet("Dawn")
    result = find_best_route(graph, "Aegis", "Caelum")
    assert result.found


if __name__ == "__main__":
    test_lmax_blocks_direct_aegis_caelum()
    test_aegis_to_caelum_routes_through_intermediate()
    test_payload_survives_multi_hop_round_trip()
    test_dynamic_rerouting_around_dead_node()
    test_full_isolation_is_undeliverable()
    test_revive_restores_route()
    print("All routing tests passed.")
