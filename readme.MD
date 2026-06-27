# Relic Ring Protocol Backend

## Overview

The Relic Ring Protocol Backend is a FastAPI-based simulation engine that models message routing across a fictional interplanetary communication network.

The system calculates optimal message routes between planets using Dijkstra's shortest-path algorithm while considering:

* Fiber ring transmission delays
* Atmospheric propagation delays
* Interplanetary vacuum transmission delays
* Tower processing delays
* Planet and link failures

The backend provides APIs for routing messages, inspecting the universe state, and simulating network failures.

---

# Technology Stack

* Python 3.13+
* FastAPI
* Uvicorn
* Pydantic
* Pytest
* NetworkX

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
cd backend
```

## Create Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirement.txt
```

---

# Dependencies

```txt
fastapi
uvicorn[standard]
pytest
networkx
```

---

# Running the Server

```bash
uvicorn app.main:app --reload --port 8000
```

API will be available at:

```txt
http://localhost:8000
```

Swagger Documentation:

```txt
http://localhost:8000/docs
```

ReDoc Documentation:

```txt
http://localhost:8000/redoc
```

---

# System Architecture

## Core Components

### app/main.py

Application entry point.

Responsibilities:

* Creates FastAPI application
* Loads universe configuration
* Enables CORS
* Registers API routes
* Stores Universe singleton in application state

---

### app/core/models.py

Contains core domain models:

#### Tower

Represents a communication tower.

Properties:

* planet_id
* index
* x_km
* y_km

Methods:

* distance_to()
* angle_rad()

#### Planet

Represents a network node.

Properties:

* id
* codex
* x_km
* y_km
* radius_km
* active_towers
* atmosphere_thickness_km
* refraction_index
* towers
* active

Methods:

* _place_towers()
* arc_length_between_towers()
* closest_tower_pair_to()
* get_tower()
* encode_to_codex()
* decode_from_codex()

---

### app/core/universe.py

Central system model.

Responsibilities:

* Load universe configuration
* Store all planets
* Simulate failures
* Calculate distances
* Validate direct communication links

Key Methods:

#### load()

Loads planets and constants from configuration.

#### get_planet()

Returns a planet by ID.

#### all_planets()

Returns all planets.

#### active_planets()

Returns active planets only.

#### kill_node()

Marks a planet as inactive.

#### restore_node()

Restores a failed planet.

#### kill_link()

Disables communication between two planets.

#### restore_link()

Restores communication link.

#### is_link_alive()

Checks if a link is active.

#### void_distance_km()

Calculates distance through space:

```text
L = center_distance - outer_radius_A - outer_radius_B
```

#### can_direct_hop()

Determines whether direct communication is possible.

---

### app/core/latency.py

Latency calculation engine.

Calculates:

#### T_fiber

Fiber ring propagation delay.

#### T_atm_src

Source atmosphere delay.

#### T_void

Interplanetary vacuum delay.

#### T_atm_dst

Destination atmosphere delay.

#### T_towers

Tower processing delay.

Total latency:

```text
T_total =
T_fiber +
T_atm_src +
T_void +
T_atm_dst +
T_towers
```

Classes:

#### HopLatency

Stores complete latency breakdown.

Methods:

* total_s
* total_ms
* breakdown()

#### LatencyEngine

Computes hop latency.

Methods:

* compute()

---

### app/core/router.py

Routing engine.

Responsibilities:

* Build communication graph
* Calculate shortest path
* Produce hop logs
* Track payload encoding transformations

Algorithm:

```text
Dijkstra Shortest Path
```

Main Classes:

#### Router

Primary routing engine.

Methods:

* route()

#### RouteResult

Stores final routing result.

Properties:

* path
* hop_log
* total_latency_ms
* undeliverable

Methods:

* to_dict()
* pretty_print()

#### HopEntry

Represents one transmission hop.

Contains:

* source planet
* destination planet
* entry tower
* sending tower
* receiving tower
* payload encoding
* latency breakdown

---

# API Endpoints

## Health

### GET /

Returns backend status.

Response:

```json
{
  "status": "online",
  "system": "Relic Ring Protocol"
}
```

---

# Universe Endpoints

## Get Full Universe

### GET /universe

Returns:

* planets
* towers
* constants
* failed nodes
* failed links

---

## Get Planet

### GET /universe/planet/{planet_id}

Returns detailed information about a specific planet.

---

# Routing Endpoints

## Route Message

### POST /route

Request:

```json
{
  "origin_id": "Aethon",
  "destination_id": "Cyra",
  "message": "Hello"
}
```

Response Includes:

* route path
* hop count
* hop-by-hop transmission log
* encoded payload
* latency breakdown
* total latency

---

# Chaos Engineering Endpoints

Used to simulate failures.

## Kill Node

### POST /chaos/kill-node/{planet_id}

Simulates planet failure.

---

## Restore Node

### POST /chaos/restore-node/{planet_id}

Restores a failed planet.

---

## Kill Link

### POST /chaos/kill-link

Request:

```json
{
  "planet_id_a": "Aethon",
  "planet_id_b": "Cyra"
}
```

Disables communication between two planets.

---

## Restore Link

### POST /chaos/restore-link

Restores a failed link.

---

## Get Chaos Status

### GET /chaos/status

Returns:

* total planets
* active planets
* failed nodes
* failed links

---

# Data Validation

Validation is handled through Pydantic schemas.

## RouteRequest

```json
{
  "origin_id": "string",
  "destination_id": "string",
  "message": "string"
}
```

Rules:

* Message cannot be empty.

---

# Features

## Routing

* Multi-hop routing
* Lowest-latency path selection
* Dijkstra shortest path algorithm

## Message Encoding

* Planet-specific codex encoding
* ASCII conversion support
* Automatic payload transformation

## Physical Simulation

* Fiber ring latency
* Atmospheric latency
* Vacuum transmission latency
* Tower processing latency

## Failure Simulation

* Node failure simulation
* Link failure simulation
* Dynamic rerouting

## Monitoring

* Universe inspection
* Planet inspection
* Failure-state tracking
* Detailed hop logging

---

# Testing

Run tests:

```bash
pytest
```

Test Modules:

```text
tests/test_api.py
tests/test_latency.py
tests/test_models.py
tests/test_router.py
```

---

# Project Structure

```text
backend/
│
├── app/
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   │
│   ├── core/
│   │   ├── constants.py
│   │   ├── latency.py
│   │   ├── models.py
│   │   ├── router.py
│   │   └── universe.py
│   │
│   └── main.py
│
├── tests/
│
├── requirement.txt
│
└── universe-config.json
```

---

# Key Functionalities Summary

* Planet-based communication simulation
* Tower placement and management
* Codex-based message encoding
* Latency-aware routing
* Dynamic shortest-path computation
* Failure simulation and recovery
* Complete route tracing
* REST API access
* Automated testing support
