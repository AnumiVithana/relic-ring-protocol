# Relic Ring Protocol — Zeta-26 Recovery Network Control Terminal

This project simulates a communications routing network to reconnect the **Zeta-26** star system following the catastrophic Hyper-Flare of 3704, which destroyed the instant-latency quantum Aether-Net. 

Relaying messages now relies on the **Relic Ring**, a primitive, physical infrastructure consisting of subsurface fiber optic rings around individual planets and long-distance void-space lasers between planets.

---

## 1. Setup & Installation

The application backend is built using Python (FastAPI + Uvicorn) and the frontend is built using standard HTML5 Canvas and Vanilla JavaScript.

### Prerequisites
*   Python 3.11 or Python 3.12 (Recommended). *Avoid Python 3.14 due to dependency compilation conflicts.*

### Installation Steps

1.  **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    ```

2.  **Activate the Virtual Environment**:
    *   **Windows (PowerShell)**
        ```powershell
        .\venv\Scripts\Activate.ps1
        ```
    *   **Linux/macOS**
        ```bash
        source venv/bin/activate
        ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

---

## 2. Running the Application

### Start the Server
Run the application from the root directory.
```bash
python run.py
```
This spins up the FastAPI app on **`http://localhost:8000`** and automatically watches files for hot-reloads.

### Access the UI
Open your web browser and navigate to:
**[http://localhost:8000](http://localhost:8000)**

---

## 3. Running Unit Tests
To verify all calculations (codex base conversions, latency math, shortest path Dijkstra routing) are accurate, run the tests.
```bash
# Run codex conversion tests
python tests/test_codex.py

# Run latency engine math tests
python tests/test_latency.py

# Run network pathfinding and chaos rerouting tests
python tests/test_routing.py
```

---

## 4. Routing Architecture (Tower-Level Graph)

A key design choice in this implementation is routing pathfinding at the **Tower-level** rather than the **Planet-level**. 

*   **Planet-level Dijkstra (Inferior)** - Finds paths based only on void distances. It completely ignores internal fiber-arc transits inside intermediate planets during path selection. This leads to inefficient routing, especially through giant planets (e.g., Caelum, which has a massive 58,232 km radius causing hundreds of milliseconds of unmodeled fiber transit latency).
*   **Tower-level Dijkstra (Implemented)** -  Graph nodes are modeled as specific planet towers `(planet_id, tower_index)`. Intra-planet fiber arcs are represented as weighted graph edges. This guarantees that Dijkstra optimizes for the *true* total end-to-end latency (fiber arc transit times + processing delays + atmospheric refraction + void transmission).

---

## 5. Physical Constants & Justifications

All constants are parsed dynamically from the `universe_metadata` section of `universe-config.json`. If a constant is missing, the engine falls back to the default values below:

| Constant | Symbol / Key in Config | Default Value | Physical Justification |
| :--- | :--- | :--- | :--- |
| **Speed of Light** | `speed_of_light_kms` | `300,000 km/s` | The fundamental speed limit of light in a vacuum ($C$), governing laser transmissions across void space. |
| **Wireless Signal Threshold** | `max_void_hop_distance_km` / `Lmax` | `50,000,000 km` | The maximum distance laser transceivers can beam coherently before signal divergence prevents data recovery. Hops exceeding this must route through intermediate relay nodes. |
| **Processing Tower Delay** | `tower_processing_delay_ms` / `Δt` | `7.0 ms` | Fixed processing delay incurred at every active tower hit (decoding, checking routing table, re-encoding, and firing). |
| **Fiber Speed Fraction** | `fiber_speed_fraction` / `f` | `0.67` | Light travels slower inside solid silica fiber optic cables than in a vacuum. The propagation speed is modeled as $0.67 \times C$ (approximately $201,000$ km/s). |
| **Coordinate Scale Factor** | `coordinate_scale_unit_km` | `1.0` | Converts abstract coordinate grid units in the configuration to actual kilometers. (*Configured to $100,000.0$ km/unit in Zeta-26 universe*). |
