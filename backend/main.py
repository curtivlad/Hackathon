"""
main.py
Serverul FastAPI — expune API REST si WebSocket pentru frontend.
"""

import asyncio
import json
import time
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation import simulation
from v2x_channel import channel

app = FastAPI(title="V2X Intersection Safety Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set cu toate conexiunile WebSocket active
active_connections: Set[WebSocket] = set()


# ------------------------------------------------------------------ #
#  WebSocket — stream de date in timp real catre frontend             #
# ------------------------------------------------------------------ #

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            state = simulation.get_full_state()
            await websocket.send_json(state)
            await asyncio.sleep(0.1)   # 10 fps
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception as e:
        active_connections.discard(websocket)


# ------------------------------------------------------------------ #
#  REST API                                                           #
# ------------------------------------------------------------------ #

@app.get("/")
def root():
    return {"status": "ok", "message": "V2X Safety Agent running"}


@app.post("/simulation/start/{scenario}")
def start_simulation(scenario: str):
    """Porneste un scenariu: blind_intersection | emergency_vehicle | multi_vehicle"""
    valid = ["blind_intersection", "emergency_vehicle", "multi_vehicle"]
    if scenario not in valid:
        return {"error": f"Unknown scenario. Use one of: {valid}"}
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
    """Snapshot curent al simularii (fallback fara WebSocket)."""
    return simulation.get_full_state()


@app.get("/simulation/scenarios")
def list_scenarios():
    return {
        "scenarios": [
            {
                "id": "blind_intersection",
                "name": "Intersectie cu vizibilitate redusa",
                "description": "2 vehicule din directii perpendiculare. B cedeaza lui A.",
                "vehicles": 2,
            },
            {
                "id": "emergency_vehicle",
                "name": "Vehicul de urgenta",
                "description": "Ambulanta vs vehicul normal. Ambulanta are prioritate.",
                "vehicles": 2,
            },
            {
                "id": "multi_vehicle",
                "name": "4 vehicule simultan",
                "description": "Toate directiile active in acelasi timp.",
                "vehicles": 4,
            },
        ]
    }


@app.get("/v2x/channel")
def get_channel():
    """Starea curenta a canalului V2X."""
    return channel.to_dict()


@app.get("/v2x/history")
def get_history(last_n: int = 50):
    """Ultimele N mesaje V2X publicate."""
    return {"history": channel.get_history(last_n)}