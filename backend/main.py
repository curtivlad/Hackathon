
import sys, os, glob, importlib
sys.dont_write_bytecode = True
for pyc in glob.glob(os.path.join(os.path.dirname(__file__), "__pycache__", "*.pyc")):
    try:
        os.remove(pyc)
    except Exception:
        pass
importlib.invalidate_caches()

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv()

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

API_TOKEN = os.getenv("API_TOKEN", "v2x-secret-token-change-in-prod")
REST_RATE_LIMIT = int(os.getenv("REST_RATE_LIMIT", "30"))


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    if simulation.running:
        simulation.stop()
    logger.info("V2X Safety Agent — shut down cleanly.")


app = FastAPI(title="V2X Intersection Safety Agent", lifespan=lifespan)


class _RestRateLimiter:

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


async def verify_token(authorization: Optional[str] = Header(None)):
    if not API_TOKEN:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


async def rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _rest_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")


ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_WS_CONNECTIONS = 10
active_connections: Set[WebSocket] = set()


def sanitize_full_state(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}

    def _safe_str(val, mx=100):
        return str(val)[:mx] if val is not None else ""

    def _safe_num(val, lo=-10000, hi=10000):
        try:
            v = float(val)
            return max(lo, min(hi, v))
        except (TypeError, ValueError):
            return 0

    def _safe_agent(a):
        if not isinstance(a, dict):
            return a
        return {
            "agent_id": _safe_str(a.get("agent_id"), 30),
            "agent_type": _safe_str(a.get("agent_type", "vehicle"), 20),
            "x": _safe_num(a.get("x", 0)),
            "y": _safe_num(a.get("y", 0)),
            "speed": _safe_num(a.get("speed", 0), 0, 200),
            "direction": _safe_num(a.get("direction", 0), 0, 360),
            "intention": _safe_str(a.get("intention", "straight"), 20),
            "risk_level": _safe_str(a.get("risk_level", "low"), 20),
            "decision": _safe_str(a.get("decision", "go"), 20),
            "reason": _safe_str(a.get("reason", ""), 50),
            "is_emergency": bool(a.get("is_emergency", False)),
            "is_police": bool(a.get("is_police", False)),
            "is_drunk": bool(a.get("is_drunk", False)),
            "pulling_over": bool(a.get("pulling_over", False)),
            "arrested": bool(a.get("arrested", False)),
            "llm_calls": int(a.get("llm_calls", 0)),
            "llm_errors": int(a.get("llm_errors", 0)),
            "memory_decisions": int(a.get("memory_decisions", 0)),
            "near_misses": int(a.get("near_misses", 0)),
            "v2x_alerts_received": int(a.get("v2x_alerts_received", 0)),
            "lessons_learned": int(a.get("lessons_learned", 0)),
        }

    agents = {}
    for k, v in raw.get("agents", {}).items():
        agents[_safe_str(k, 30)] = _safe_agent(v)

    pairs = []
    for p in raw.get("collision_pairs", []):
        pairs.append({
            "agent1": _safe_str(p.get("agent1"), 30),
            "agent2": _safe_str(p.get("agent2"), 30),
            "risk": _safe_str(p.get("risk", "low"), 20),
            "ttc": _safe_num(p.get("ttc", 999), 0, 9999),
        })

    return {
        "scenario": _safe_str(raw.get("scenario"), 50),
        "running": bool(raw.get("running", False)),
        "agents": agents,
        "infrastructure": raw.get("infrastructure", {}),
        "collision_pairs": pairs,
        "stats": raw.get("stats", {}),
        "timestamp": _safe_num(raw.get("timestamp", 0), 0, 9999999999),
        "grid": raw.get("grid", None),
        "background_traffic": bool(raw.get("background_traffic", False)),
        "traffic_light_intersections": raw.get("traffic_light_intersections", []),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    if API_TOKEN and token != API_TOKEN:
        logger.warning("[SECURITY] WebSocket REFUZAT — token invalid sau lipsa")
        await websocket.accept()
        await websocket.close(code=1008, reason="Unauthorized")
        return

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
            safe_state = sanitize_full_state(raw_state)
            await websocket.send_json(safe_state)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


VALID_SCENARIOS = frozenset([
    "emergency_vehicle", "emergency_vehicle_no_lights",
    "right_of_way", "multi_vehicle_traffic_light",
    "drunk_driver",
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
                "id": "multi_vehicle_traffic_light",
                "name": "4 Vehicule — Cu Semafor",
                "description": "4 vehicule din toate directiile cu semafor activ.",
                "vehicles": 4,
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
    import random
    from agents import VehicleAgent
    from background_traffic import _build_route, _ALL_ROUTE_KEYS

    route_key = random.choice(_ALL_ROUTE_KEYS)
    waypoints, direction = _build_route(route_key)
    if len(waypoints) < 2:
        return {"error": "Could not find a valid route"}

    start_x, start_y = waypoints[0]
    speed = random.uniform(8.0, 12.0)

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

    simulation.vehicles.append(vehicle)
    simulation.stats["total_vehicles"] += 1
    vehicle.start()

    logger.info(f"[DRUNK] Spawned {agent_id} at ({start_x:.0f}, {start_y:.0f}) dir={direction}")
    return {"status": "spawned", "agent_id": agent_id, "x": start_x, "y": start_y, "direction": direction}


@app.post("/simulation/spawn-police", dependencies=[Depends(verify_token), Depends(rate_limit)])
def spawn_police_car():
    import random
    from agents import VehicleAgent
    from background_traffic import _build_route, _ALL_ROUTE_KEYS

    route_key = random.choice(_ALL_ROUTE_KEYS)
    waypoints, direction = _build_route(route_key)
    if len(waypoints) < 2:
        return {"error": "Could not find a valid route"}

    start_x, start_y = waypoints[0]
    speed = random.uniform(20.0, 25.0)

    if not hasattr(spawn_police_car, '_counter'):
        spawn_police_car._counter = 0
    spawn_police_car._counter += 1
    agent_id = f"POLICE_{spawn_police_car._counter:03d}"

    vehicle = VehicleAgent(
        agent_id=agent_id,
        start_x=start_x,
        start_y=start_y,
        direction=direction,
        initial_speed=speed,
        target_speed=speed,
        intention="straight",
        is_police=True,
        waypoints=waypoints[1:],
    )

    simulation.vehicles.append(vehicle)
    simulation.stats["total_vehicles"] += 1
    vehicle.start()

    logger.info(f"[POLICE] Spawned {agent_id} at ({start_x:.0f}, {start_y:.0f}) dir={direction}")
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
    last_n = max(1, min(last_n, 500))
    return {"history": channel.get_history(last_n)}


@app.get("/telemetry/report", dependencies=[Depends(verify_token)])
def get_telemetry_report():
    from telemetry import telemetry
    return telemetry.generate_report()


@app.post("/telemetry/export", dependencies=[Depends(verify_token), Depends(rate_limit)])
def export_telemetry():
    from telemetry import telemetry
    filepath = telemetry.export_to_file()
    return {"status": "exported", "filepath": filepath}


@app.get("/telemetry/history", dependencies=[Depends(verify_token)])
def get_telemetry_history(last_n: int = 10):
    from telemetry import telemetry
    last_n = max(1, min(last_n, 50))
    return {"reports": telemetry.get_history(last_n)}


@app.get("/security/stats", dependencies=[Depends(verify_token)])
def security_stats():
    from llm_brain import get_circuit_breaker_stats
    result = {
        "v2x_channel": channel.get_security_stats(),
        "ws_connections": len(active_connections),
        "ws_max_connections": MAX_WS_CONNECTIONS,
        "auth_enabled": bool(API_TOKEN),
        "rest_rate_limit_per_min": REST_RATE_LIMIT,
        "llm_circuit_breaker": get_circuit_breaker_stats(),
    }
    try:
        result["intersection_coordinator"] = bg_traffic._coordinator.get_stats()
    except Exception:
        pass
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
