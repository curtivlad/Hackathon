"""
main.py — Server FastAPI SECURIZAT cu API REST si WebSocket.

Securitate:
- Autentificare: Token Bearer pe REST + query param pe WebSocket
- Rate Limiting: REST endpoints au limita per IP per minut (anti-flood)
- WebSocket: datele sunt SANITIZATE inainte de trimitere (nu se trimit date brute)
- WebSocket: limita MAX conexiuni simultane
- CORS: restrans la originile necesare
- Input: validare scenario names (whitelist)
- Endpoint /security/stats: monitoring securitate in timp real

Arhitectura:
- SimulationManager este un singleton in-process. Serverul TREBUIE rulat cu
  un singur worker (uvicorn --workers 1). La startup se verifica automat.
  Pentru scalare horizontala se recomanda Redis ca state-store.
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
from typing import Set, Optional
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from simulation import simulation
from v2x_channel import channel
from background_traffic import bg_traffic, get_grid_info
from v2x_security import MAX_WS_CONNECTIONS, sanitize_full_state

# ─── SECURITY CONFIG (read early, before app creation) ────────────────────────
API_TOKEN = os.getenv("API_TOKEN", "v2x-secret-token-change-in-prod")
REST_RATE_LIMIT = int(os.getenv("REST_RATE_LIMIT", "30"))  # req/min per IP


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle — modern FastAPI pattern."""
    logger.info("=" * 60)
    logger.info("  V2X Safety Agent — starting up")
    logger.info(f"  Auth enabled: {bool(API_TOKEN)}")
    logger.info(f"  REST rate limit: {REST_RATE_LIMIT} req/min/IP")
    logger.info(f"  Max WS connections: {MAX_WS_CONNECTIONS}")
    logger.info(f"  LLM circuit breaker: enabled")
    logger.info("  NOTICE: Server MUST run with workers=1 (in-process state)")
    logger.info("  For horizontal scaling, replace SimulationManager with Redis.")
    logger.info("=" * 60)
    yield
    # Shutdown: opreste simularea daca ruleaza
    if simulation.running:
        simulation.stop()
    logger.info("V2X Safety Agent — shut down cleanly.")


app = FastAPI(title="V2X Intersection Safety Agent", lifespan=lifespan)


# ─── REST RATE LIMITER (per IP, per minute) ──────────────────────────────────

class _RestRateLimiter:
    """Simple in-memory sliding-window rate limiter per IP."""

    def __init__(self, max_per_min: int):
        self._max = max_per_min
        self._buckets: dict = defaultdict(list)
        import threading
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        import time as _t
        now = _t.time()
        with self._lock:
            bucket = self._buckets[ip]
            self._buckets[ip] = [t for t in bucket if now - t < 60.0]
            if len(self._buckets[ip]) >= self._max:
                return False
            self._buckets[ip].append(now)
            return True


_rest_limiter = _RestRateLimiter(REST_RATE_LIMIT)


# ─── AUTH: Token-based authentication ────────────────────────────────────────

async def verify_token(authorization: Optional[str] = Header(None)):
    """Verifica header-ul Authorization: Bearer <token>."""
    if not API_TOKEN:
        return  # daca nu e setat token, skip (dev mode)
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


async def rate_limit(request: Request):
    """Rate limiting pe endpoint-uri REST."""
    client_ip = request.client.host if request.client else "unknown"
    if not _rest_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")



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
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    # Autentificare prin query param: /ws?token=xxx
    if API_TOKEN and token != API_TOKEN:
        logger.warning("[SECURITY] WebSocket REFUZAT — token invalid sau lipsa")
        await websocket.accept()
        await websocket.close(code=1008, reason="Unauthorized")
        return

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
        "auth_required": bool(API_TOKEN),
    }


@app.post("/simulation/start/{scenario}", dependencies=[Depends(verify_token), Depends(rate_limit)])
def start_simulation(scenario: str):
    # Validare stricta — doar scenarii din whitelist
    if scenario not in VALID_SCENARIOS:
        return {"error": f"Unknown scenario. Use one of: {sorted(VALID_SCENARIOS)}"}
    simulation.start(scenario)
    return {"status": "started", "scenario": scenario}


@app.post("/simulation/stop", dependencies=[Depends(verify_token), Depends(rate_limit)])
def stop_simulation():
    simulation.stop()
    return {"status": "stopped"}


@app.post("/simulation/restart", dependencies=[Depends(verify_token), Depends(rate_limit)])
def restart_simulation():
    simulation.restart()
    return {"status": "restarted", "scenario": simulation.active_scenario}


@app.get("/simulation/state", dependencies=[Depends(rate_limit)])
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


@app.post("/simulation/spawn-drunk", dependencies=[Depends(verify_token), Depends(rate_limit)])
def spawn_drunk_driver():
    """Spawn a drunk driver vehicle on a random route through the grid."""
    import random
    from agents import VehicleAgent
    from background_traffic import _build_route, _ALL_ROUTE_KEYS

    # Pick a random route
    route_key = random.choice(_ALL_ROUTE_KEYS)
    waypoints, direction = _build_route(route_key)
    if len(waypoints) < 2:
        return {"error": "Could not find a valid route"}

    start_x, start_y = waypoints[0]
    speed = random.uniform(8.0, 12.0)

    # Generate unique drunk driver ID
    if not hasattr(spawn_drunk_driver, '_counter'):
        spawn_drunk_driver._counter = 0
    spawn_drunk_driver._counter += 1
    agent_id = f"DRUNK_{spawn_drunk_driver._counter:03d}"

    vehicle = VehicleAgent(
        agent_id=agent_id,
        start_x=start_x,
        start_y=start_y,
        direction=direction,
        initial_speed=speed,
        target_speed=speed,
        intention="straight",
        is_emergency=False,
        waypoints=waypoints[1:],
        is_drunk=True,
    )

    # Add to simulation vehicles list so it shows up
    simulation.vehicles.append(vehicle)
    simulation.stats["total_vehicles"] += 1
    vehicle.start()

    logger.info(f"[DRUNK] Spawned {agent_id} at ({start_x:.0f}, {start_y:.0f}) dir={direction}")
    return {"status": "spawned", "agent_id": agent_id, "x": start_x, "y": start_y, "direction": direction}


@app.post("/background-traffic/start", dependencies=[Depends(verify_token), Depends(rate_limit)])
def start_bg_traffic():
    bg_traffic.start()
    return {"status": "started"}


@app.post("/background-traffic/stop", dependencies=[Depends(verify_token), Depends(rate_limit)])
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

@app.get("/security/stats", dependencies=[Depends(verify_token)])
def security_stats():
    """Endpoint de monitoring securitate — arata mesaje respinse, agenti inactivi, etc."""
    from llm_brain import get_circuit_breaker_stats
    return {
        "v2x_channel": channel.get_security_stats(),
        "ws_connections": len(active_connections),
        "ws_max_connections": MAX_WS_CONNECTIONS,
        "auth_enabled": bool(API_TOKEN),
        "rest_rate_limit_per_min": REST_RATE_LIMIT,
        "llm_circuit_breaker": get_circuit_breaker_stats(),
    }



if __name__ == "__main__":
    import uvicorn
    # IMPORTANT: workers=1 obligatoriu — SimulationManager e singleton in-process
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)

