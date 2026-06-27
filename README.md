# Relic Ring Protocol — Zeta-26 Recovery Network Control Terminal

This project simulates a communications routing network to reconnect the **Zeta-26** star system following the catastrophic Hyper-Flare of 3704, which destroyed the instant-latency quantum Aether-Net. 

Relaying messages now relies on the **Relic Ring**—a primitive, physical infrastructure consisting of subsurface fiber optic rings around individual planets and long-distance void-space lasers between planets.

---

## 1. Running the Application

### Option 1: Run with Docker (Recommended / Quickest)

You can spin up the entire application (backend + web UI) instantly without installing Python or dependencies on your local machine using Docker.

1.  **Launch Docker Desktop**: Make sure your Docker Desktop daemon is running.
2.  **Start the Container**: Run this command from the project root directory:
    ```bash
    docker compose up --build
    ```
    *This command compiles the environment, sets up port mapping, and boots the server.*
3.  **Access the UI**: Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.
4.  **Stop the Container**: Press `Ctrl+C` in your terminal, or run `docker compose down`.

*Note: The Docker Compose setup mounts your local `universe-config.json` as a volume. Any changes you make to the configuration locally are immediately reflected inside the running container without requiring a rebuild!*

---

### Option 2: Run Locally (Python Virtual Environment)

If you prefer to run the application natively on your system:

#### Prerequisites
*   Python 3.11 or Python 3.12 (Recommended). *Avoid Python 3.14 due to dependency compilation conflicts (e.g. pydantic-core/pyo3).*

#### Setup Steps
1.  **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    ```
2.  **Activate the Virtual Environment**:
    *   **Windows (PowerShell)**:
        ```powershell
        .\venv\Scripts\Activate.ps1
        ```
    *   **Linux/macOS**:
        ```bash
        source venv/bin/activate
        ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Start the Server**:
    ```bash
    python run.py
    ```
5.  **Access the UI**: Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 2. Running Unit Tests
To verify all calculations (codex base conversions, latency math, shortest path Dijkstra routing) are accurate, run the tests using your local python environment:
```bash
# Run codex conversion tests
python tests/test_codex.py

# Run latency engine math tests
python tests/test_latency.py

# Run network pathfinding and chaos rerouting tests
python tests/test_routing.py
```

---

## 3. Routing Architecture (Tower-Level Graph)

A key design choice in this implementation is routing pathfinding at the **Tower-level** rather than the **Planet-level**. 

*   **Planet-level Dijkstra (Inferior)**: Finds paths based only on void distances. It completely ignores internal fiber-arc transits inside intermediate planets during path selection. This leads to inefficient routing, especially through giant planets (e.g., Caelum, which has a massive 58,232 km radius causing hundreds of milliseconds of unmodeled fiber transit latency).
*   **Tower-level Dijkstra (Implemented)**: Graph nodes are modeled as specific planet towers `(planet_id, tower_index)`. Intra-planet fiber arcs are represented as weighted graph edges. This guarantees that Dijkstra optimizes for the *true* total end-to-end latency (fiber arc transit times + processing delays + atmospheric refraction + void transmission).

---

## 4. Physical Constants & Justifications

All constants are parsed dynamically from the `universe_metadata` section of `universe-config.json`. If a constant is missing, the engine falls back to the default values below:

| Constant | Symbol / Key in Config | Default Value | Physical Justification |
| :--- | :--- | :--- | :--- |
| **Speed of Light** | `speed_of_light_kms` | `300,000 km/s` | The fundamental speed limit of light in a vacuum ($C$), governing laser transmissions across void space. |
| **Wireless Signal Threshold** | `max_void_hop_distance_km` / `Lmax` | `50,000,000 km` | The maximum distance laser transceivers can beam coherently before signal divergence prevents data recovery. Hops exceeding this must route through intermediate relay nodes. |
| **Processing Tower Delay** | `tower_processing_delay_ms` / `Δt` | `7.0 ms` | Fixed processing delay incurred at every active tower hit (decoding, checking routing table, re-encoding, and firing). |
| **Fiber Speed Fraction** | `fiber_speed_fraction` / `f` | `0.67` | Light travels slower inside solid silica fiber optic cables than in a vacuum. The propagation speed is modeled as $0.67 \times C$ (approximately $201,000$ km/s). |
| **Coordinate Scale Factor** | `coordinate_scale_unit_km` | `1.0` | Converts abstract coordinate grid units in the configuration to actual kilometers. (*Configured to $100,000.0$ km/unit in Zeta-26 universe*). |
