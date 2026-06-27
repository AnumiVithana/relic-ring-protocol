# Relic Ring Protocol

> A latency-accurate, fault-tolerant routing simulator for the Zeta-26 star system.

After the Hyper-Flare of 3704 destroyed the instant, zero-latency Aether-Net, the only thing left connecting Zeta-26's six worlds is the **Relic Ring**, a patchwork of underground fiber rings, laser transceivers, and incompatible numeral systems built by the system's earliest colonists. This project simulates that network. It routes packets between planets, calculates real physical latency (fiber transit, tower processing delay, atmospheric refraction, vacuum laser transit), translates payloads between each planet's numeric dialect, and survives node/link failures by rerouting live.

Live link :- https://thamarabhagya-relic-ring-protocol.hf.space/

---

## Table of Contents

- [What this actually does](#what-this-actually-does)
- [How the network works](#how-the-network-works)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Dockerization setup](#dockerization-setup)
- [Running it](#running-it)
- [Using the dashboard](#using-the-dashboard)
- [API reference](#api-reference)
- [The math, explained](#the-math-explained)
- [Design decisions and assumptions](#design-decisions-and-assumptions)
- [Running tests](#running-tests)
- [Known limitations](#known-limitations)

---

## What this actually does

Given a `universe-config.json` describing a star system (planets, their towers, their numeric "codex" base, and physical constants), this system,

1. **Builds a routing graph** at the level of individual towers, not just planets, so the shortest-latency path correctly accounts for which tower a packet enters and exits on each world.
2. **Calculates real latency** for any route using four physical components: fiber-arc transit inside a planet, per-tower processing delay, atmospheric refraction slowdown, and vacuum laser transit time.
3. **Enforces a maximum void-hop distance (`Lmax`)** — if two planets are too far apart for a direct laser link, the packet must be routed through an intermediate world, or the system reports the message as undeliverable.
4. **Translates the payload** at every hop — ASCII inside a planet's internal routing, converted into the destination planet's numeric base before crossing the void.
5. **Survives failures** — you can "kill" a planet or a link mid-simulation, and any packet sent afterward automatically reroutes around the dead zone, or correctly reports undeliverable if no path exists.
6. **Visualizes all of this** in a browser dashboard: an interactive orbital map, a live hop-by-hop log proving the route taken, and a latency breakdown chart.

---

## How the network works

```
ORIGIN PLANET
  message is generated, encoded into the NEXT hop's numeric base
        |
        |  laser transit across the void (T_v)
        v
RELAY PLANET
  decoded back to ASCII, routed tower-to-tower internally (T_p),
  re-encoded for the next hop
        |
        |  ... repeats for each intermediate planet ...
        v
DESTINATION PLANET
  decoded one final time, payload delivered
```

Every hop produces an entry in the packet's `hop_log`, so the full route which planet, which tower, what the payload looked like at that exact moment, is provable after the fact.

---

## Project structure

```
relic-ring-protocol/
├── universe-config.json     the star system being simulated
├── requirements.txt
├── run.py                    entry point, starts the web server
│
├── app/
│   ├── config.py             loads and validates universe-config.json
│   ├── models.py              Packet, HopLogEntry data structures
│   ├── geometry.py            tower placement on each planet's ring
│   ├── latency.py              the physics: T_v, T_p, void distance L
│   ├── codex.py                 numeric base conversion (the "dialects")
│   ├── universe.py              builds the tower-level routing graph
│   ├── routing.py                Dijkstra shortest-latency pathfinding
│   ├── network.py                 orchestrates a full packet send, hop by hop
│   ├── api.py                      FastAPI server (REST + WebSocket)
│   └── static/
│       ├── index.html               the dashboard
│       ├── style.css                 terminal/control-room visual theme
│       └── app.js                     canvas map rendering + live updates
│
└── tests/
    ├── test_codex.py          validates base conversion against the brief's worked example
    ├── test_latency.py         validates the latency formulas
    └── test_routing.py          validates Lmax enforcement, rerouting, undeliverable cases
```

---

## Setup

**Requirements:** Python 3.10 or newer (the codebase uses modern type-hint syntax like `str | None`).

1. Clone or unzip the project, then move into the project folder

   ```bash
   cd relic-ring-protocol
   ```

2. Create a virtual environment

   ```bash
   python -m venv venv
   source venv/bin/activate        # on Windows: venv\Scripts\activate
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

That's it. No database, no external services, no API keys.

---

## Dockerization setup

If you prefer running the simulator in containers, this repository already includes both a `Dockerfile` and a `docker-compose.yml`.

### Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- Port `8000` available on your machine

### Start with Docker Compose

From the project root,

```bash
docker compose up --build
```

Then open **http://localhost:8000**.

What this does

- Builds the image from `Dockerfile`
- Starts the `relic-ring-terminal` service
- Maps container port `8000` to host port `8000`
- Mounts your local `universe-config.json` into the container, so universe edits apply without rebuilding the image

### Run in detached mode

```bash
docker compose up --build -d
```

Useful follow-up commands

```bash
docker compose logs -f
docker compose ps
docker compose down
```

### Rebuild after dependency/code changes

If you change dependencies (for example in `requirements.txt`) or container build steps.

```bash
docker compose up --build -d
```

To force a fresh rebuild with no cache.

```bash
docker compose build --no-cache
docker compose up -d
```

### Optional: run with plain Docker (no Compose)

```bash
docker build -t relic-ring-protocol .
docker run --rm -p 8000:8000 -v "${PWD}/universe-config.json:/workspace/universe-config.json" relic-ring-protocol
```

On Windows PowerShell, if `${PWD}` causes path issues, use:

```powershell
docker run --rm -p 8000:8000 -v "${PWD.Path}\universe-config.json:/workspace/universe-config.json" relic-ring-protocol
```

---

## Running it

```bash
python run.py
```

Then open **http://localhost:8000** in a browser.

The server auto-reloads on code changes, which is handy while developing. To stop it, press `Ctrl+C`.

Want a different universe? Edit `universe-config.json` and restart the server. Nothing is hardcoded; every planet and constant is read from that file at startup.

---

## Using the dashboard

**Orbital Grid** — The live map. Drag to pan, scroll to zoom, click a planet to set it as your destination. Cyan lines are working void links; red dashed lines are pairs too far apart to link directly (`Lmax` exceeded).

**Transmit Packet** — Pick an origin, a destination, type a message, hit Transmit. Watch the packet animate hop-by-hop across the map.

**Chaos Test** — Pick a planet and hit Kill Node to simulate a hardware failure. Send a packet again — it reroutes around the dead planet automatically, or reports undeliverable if there's no other path. Hit Revive to bring it back.

**Hop Log & Latency Breakdown** — After any transmission, this table shows every tower the packet touched, what the payload looked like at each step (ASCII vs. encoded), and a chart breaking total latency into fiber transit, tower processing, and void/atmosphere time.

---

## API reference

All endpoints are plain JSON over HTTP, plus one WebSocket for live updates.

### `GET /api/universe`

Returns the full current state: every planet (with tower positions), every void link (with distance and blocked/alive status), and any currently-failed nodes/links.

### `POST /api/send`

```json
{ "origin": "Aegis", "destination": "Caelum", "message": "Hello world" }
```

Returns the delivery result, the planet path taken, the full `hop_log`, and the latency breakdown. If no route exists, `delivered` is `false` with a `reason`.

### `POST /api/chaos/kill-node`

```json
{ "planet_id": "Dawn" }
```

Marks a planet offline. Any tower on it becomes unreachable.

### `POST /api/chaos/revive-node`

```json
{ "planet_id": "Dawn" }
```

Brings a planet back online.

### `POST /api/chaos/kill-link` and `POST /api/chaos/revive-link`

```json
{ "planet_a": "Aegis", "planet_b": "Boreas" }
```

Fails or restores a specific void link without touching either planet.

### `WS /ws`

Broadcasts `node_killed`, `node_revived`, and `packet_sent` events to every connected client. Open the dashboard in two browser tabs and kill a node in one to see the other update live.

---

## The math, explained

Every constant below (`speed_of_light_kms`, `tower_processing_delay_ms`, `max_void_hop_distance_km`, `fiber_speed_fraction`, `coordinate_scale_unit_km`) is read from `universe_metadata` in the config file. The values used in this section are just the documented fallback defaults if a field is ever missing.

### 1. Void distance: how far apart two planets actually are

```
L = distance_between_centers_km - (R1 + h1) - (R2 + h2)
```

Planet coordinates are in abstract grid units, so they're first multiplied by `coordinate_scale_unit_km` to get real kilometers. Then both planets' radius and atmosphere thickness are subtracted, because the laser only has to cross the gap between the outer edges of each planet's atmosphere, not the full center-to-center distance.

### 2. Void travel time: how long the laser takes to get there

```
T_v = (h1 x n1 + h2 x n2 + L) / C
```

The atmosphere slows the signal down (each planet's `refraction_index`, n), and the rest of the trip is vacuum at the speed of light, C. This is a per-hop cost. Every time a packet crosses from one planet to another, this formula runs once.

### 3. Internal crust transit: how long it takes to cross a planet between towers

```
T_p = (fiber-arc distance between entry and exit tower) / (fiber_speed_fraction x C)  +  (tower delay x number of distinct towers touched)
```

Towers sit evenly spaced around each planet's equator, numbered clockwise starting at the top. When a packet arrives at one tower and needs to leave from a different tower to reach the next planet, it travels along the fiber arc between them at `0.67c` by default. Every distinct tower it touches costs a fixed `7 ms` processing delay, but if the entry and exit tower happen to be the same one, that delay is only paid once.

At the very start and very end of a journey (the origin and destination planets), there's no entry/exit pair to travel between. The packet just touches one tower and pays one delay.

### 4. Putting a full route together

```
Total latency = (one T_p for every planet visited) + (one T_v for every void hop between them)
```

The system runs Dijkstra's algorithm over a graph built at the tower level, not the planet level, so this entry/exit tower accounting falls out naturally from the shortest path itself rather than needing special-casing.

### 5. Codex translation: crossing the dialect barrier

Each planet receives data in its own numeric base (its "codex"). A message is converted character by character: the raw text becomes ASCII byte values internally, and before crossing the void, each byte is converted independently into the destination planet's base. On arrival, the planet decodes it straight back to ASCII to route it internally, then re-encodes it again for whichever planet is next.

For example, the letter `H` (ASCII 72) becomes `"242"` heading to a base-5 planet, or `"52"` heading to a base-14 planet, and decodes back to `72` then `H` on arrival, no matter how many hops it takes.

---

## Design decisions and assumptions

The challenge brief leaves a few things to engineering judgment. Here's what was decided and why:

- **Tower-level graph, not planet-level.** Routing nodes are individual `(planet, tower_index)` pairs rather than whole planets. This means Dijkstra's shortest path naturally and correctly accounts for which tower a packet enters and exits on every planet along the route, without needing to special-case the internal fiber-arc cost separately from the void-hop cost.
- **Line-of-sight tower selection doesn't affect the distance formula.** Per the brief's "Void Distance Simplification" note, the closest tower pair between two planets determines which towers send and receive (for logging and for the internal fiber-arc calculation) but never changes the void distance `L` itself. `L` is always computed from planet centers, radii, and atmosphere thickness only.
- **One tower delay per distinct tower touched.** If a packet's entry and exit tower on a relay planet happen to be the same tower, only one `7 ms` delay is charged. If they differ, two delays are charged, one on arrival and one on departure. This matches the brief's rule that a tower hit by both receiving and sending is only charged once.
- **Origin and destination planets pay exactly one tower delay each**, since there's no internal arc to travel. The packet is simply generated at, or finally decoded at, a single tower.
- **`Lmax` blocks the edge entirely, rather than penalizing it.** If two planets' void distance exceeds the configured maximum hop distance, no direct link is created in the routing graph at all. The only way to connect them is through an intermediate planet, exactly as the brief specifies. If no such planet exists, the route is reported as undeliverable rather than the system crashing or silently failing.
- **No constants are hardcoded.** Every physical constant is read from `universe_metadata` in the config file, with the brief's documented values used only as fallback defaults if a field is absent.

---

## Running tests

```bash
python tests/test_codex.py
python tests/test_latency.py
python tests/test_routing.py
```

What's covered:

- **`test_codex.py`** — base conversion matches the brief's exact "Hello world" to Base 5 / Base 14 worked example, plus round-trip correctness across a dozen different bases.
- **`test_latency.py`** — the void distance, void travel time, and crust transit formulas match hand-calculated expected values.
- **`test_routing.py`** — confirms `Lmax` actually blocks the direct Aegis-Caelum link, confirms multi-hop routing succeeds anyway, confirms a packet's payload survives a full round trip intact, and confirms the system reroutes around a killed node (or correctly reports undeliverable when a planet is fully isolated).

---

## Known limitations

- The dashboard's packet animation speed is for visual pacing only. It does not literally play back at the simulated millisecond latency, since some latencies are tens of seconds and nobody wants to watch that in real time.
- Failures are in-memory only. Restarting the server resets all planets and links back online.
- This is a single-universe simulator: it loads one `universe-config.json` at startup. Swapping universes means editing the file and restarting.

---

*Launch26, IEEE Computer Society, University of Kelaniya.*
