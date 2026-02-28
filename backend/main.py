"""
main.py — Server FastAPI SECURIZAT cu API REST si WebSocket.

Securitate:
- WebSocket: datele sunt SANITIZATE inainte de trimitere (nu se trimit date brute)
- WebSocket: limita MAX conexiuni simultane
- CORS: restrans la originile necesare
- Input: validare scenario names (whitelist)
- Endpoint /security/stats: monitoring securitate in timp real
"""

import sys, os, glob, importlib
sys.dont_write_bytecode = True
for pyc in glob.glob(os.path.join(os.path.dirname(__file__), "__pycache__", "*.pyc")):
    try:
        os.remove(pyc)
    except Exception:
        pass
importlib.invalidate_caches()

# Load .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv()  # also try local .env

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

import asyncio
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation import simulation
from v2x_channel import channel
from background_traffic import bg_traffic, get_grid_info

app = FastAPI(title="V2X Intersection Safety Agent")

# ─── CORS: restrans la frontend-uri cunoscute ───────────────────────────────
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─── WebSocket: conexiuni cu limita + sanitizare ────────────────────────────
active_connections: Set[WebSocket] = set()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Limita conexiuni
    if len(active_connections) >= MAX_WS_CONNECTIONS:
        logger.warning(f"[SECURITY] WebSocket REFUZAT — max {MAX_WS_CONNECTIONS} conexiuni atinse")
        await websocket.close(code=1013, reason="Too many connections")
        return

    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"[WS] Conexiune acceptata ({len(active_connections)}/{MAX_WS_CONNECTIONS})")
    try:
        while True:
            raw_state = simulation.get_full_state()
            # SANITIZARE: nu trimitem date brute, ci validate si curatate
            safe_state = sanitize_full_state(raw_state)
            await websocket.send_json(safe_state)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


# ─── API Endpoints cu validare input ────────────────────────────────────────

VALID_SCENARIOS = frozenset([
    "blind_intersection", "emergency_vehicle", "emergency_vehicle_no_lights",
    "right_of_way", "multi_vehicle", "multi_vehicle_traffic_light",
])


@app.get("/")
def root():
    from llm_brain import LLM_ENABLED, LLM_MODEL, GEMINI_API_KEY
    has_key = bool(GEMINI_API_KEY) and "INLOCUIESTE" not in GEMINI_API_KEY
    return {
        "status": "ok",
        "message": "V2X Safety Agent running",
        "llm_enabled": LLM_ENABLED,
        "llm_model": LLM_MODEL if LLM_ENABLED else None,
        "llm_api_key_set": has_key,
        "security": "enabled",
    }


@app.post("/simulation/start/{scenario}")
def start_simulation(scenario: str):
    # Validare stricta — doar scenarii din whitelist
    if scenario not in VALID_SCENARIOS:
        return {"error": f"Unknown scenario. Use one of: {sorted(VALID_SCENARIOS)}"}
    simulation.start(scenario)
    return {"status": "started", "scenario": scenario}


@app.post("/simulation/stop")
def stop_simulation():
    simulation.stop()
    return {"status": "stopped"}


@app.post("/simulation/restart")
def restart_simulation():
    simulation.restart()
    return {"status": "restarted", "scenario": simulation.active_scenario}


@app.get("/simulation/state")
def get_state():
    raw = simulation.get_full_state()
    return sanitize_full_state(raw)


@app.get("/simulation/scenarios")
def list_scenarios():
    return {
        "scenarios": [
            {
                "id": "right_of_way",
                "name": "3 Vehicule — Prioritate de Dreapta",
                "description": "3 vehicule din 3 directii, fara semafor. Negociere prin regula prioritatii de dreapta.",
                "vehicles": 3,
            },
            {
                "id": "multi_vehicle",
                "name": "4 Vehicule — Prioritate de Dreapta (Fara Semafor)",
                "description": "4 vehicule din toate directiile, fara semafor. Negociere prin regula prioritatii de dreapta.",
                "vehicles": 4,
            },
            {
                "id": "multi_vehicle_traffic_light",
                "name": "4 Vehicule — Cu Semafor",
                "description": "4 vehicule din toate directiile cu semafor activ.",
                "vehicles": 4,
            },
            {
                "id": "blind_intersection",
                "name": "Intersectie cu vizibilitate redusa",
                "description": "2 vehicule din directii perpendiculare. B cedeaza lui A.",
                "vehicles": 2,
            },
            {
                "id": "emergency_vehicle",
                "name": "Ambulanta — Cu Semafor",
                "description": "Ambulanta vs vehicul normal cu semafor activ. Semaforul se adapteaza la urgenta.",
                "vehicles": 2,
            },
            {
                "id": "emergency_vehicle_no_lights",
                "name": "Ambulanta — Fara Semafor",
                "description": "Ambulanta vs vehicul normal fara semafor. Prioritate negociata prin V2X.",
                "vehicles": 2,
            },
        ]
    }


@app.get("/v2x/channel")
def get_channel():
    return channel.to_dict()


@app.post("/background-traffic/start")
def start_bg_traffic():
    bg_traffic.start()
    return {"status": "started"}


@app.post("/background-traffic/stop")
def stop_bg_traffic():
    bg_traffic.stop()
    return {"status": "stopped"}


@app.get("/grid")
def get_grid():
    return get_grid_info()


@app.get("/v2x/history")
def get_history(last_n: int = 50):
    # Validare input
    last_n = max(1, min(last_n, 500))
    return {"history": channel.get_history(last_n)}


# ─── Security monitoring endpoint ──────────────────────────────────────────

@app.get("/security/stats")
def security_stats():
    """Endpoint de monitoring securitate — arata mesaje respinse, agenti inactivi, etc."""
    return {
        "v2x_channel": channel.get_security_stats(),
        "ws_connections": len(active_connections),
        "ws_max_connections": MAX_WS_CONNECTIONS,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
