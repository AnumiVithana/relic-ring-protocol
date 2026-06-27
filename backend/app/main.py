"""
Relic Ring Protocol — FastAPI Application Entry Point

Start with:
    uvicorn app.main:app --reload --port 8000

Endpoints:
    GET  /                          health check
    GET  /universe                  full universe state
    POST /route                     route a message
    POST /chaos/kill-node/{id}      simulate node failure
    POST /chaos/kill-link           simulate link failure
    POST /chaos/restore-node/{id}   restore a dead node
    POST /chaos/restore-link        restore a dead link
    GET  /chaos/status              current failure state
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.universe import Universe
from .api.routes import router as api_router

# ── Bootstrap universe (singleton for the app lifetime) ──────────────────────

CONFIG_PATH = Path(__file__).parent.parent.parent / "universe-config.json"

# Fallback: if running tests from backend/, look one level up
if not CONFIG_PATH.exists():
    CONFIG_PATH = Path(__file__).parent.parent / "universe-config.json"
if not CONFIG_PATH.exists():
    CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "universe-config.json"
universe = Universe.load(CONFIG_PATH)

# ── App factory ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Relic Ring Protocol",
    description="Routing simulation for the Zeta-26 star system.",
    version="1.0.0",
)

# Allow React dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach universe to app state so routes can access it
app.state.universe = universe

# Register all routes
app.include_router(api_router)


@app.get("/", tags=["Health"])
def health():
    return {
        "status": "online",
        "system": "Relic Ring Protocol",
        "planets": len(universe.planets),
        "active_planets": len(universe.active_planets()),
    }
