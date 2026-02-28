"""
main.py — Server FastAPI cu API REST si WebSocket pentru frontend.
"""

import sys, os, glob, importlib
sys.dont_write_bytecode = True
for pyc in glob.glob(os.path.join(os.path.dirname(__file__), "__pycache__", "*.pyc")):
    try:
        os.remove(pyc)
    except Exception:
        pass
importlib.invalidate_caches()

import asyncio
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

active_connections: Set[WebSocket] = set()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            state = simulation.get_full_state()
            await websocket.send_json(state)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


@app.get("/")
def root():
    return {"status": "ok", "message": "V2X Safety Agent running"}


@app.post("/simulation/start/{scenario}")
def start_simulation(scenario: str):
    valid = ["blind_intersection", "emergency_vehicle", "emergency_vehicle_no_lights", "right_of_way", "multi_vehicle", "multi_vehicle_traffic_light"]
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
    return simulation.get_full_state()


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


@app.get("/v2x/history")
def get_history(last_n: int = 50):
    return {"history": channel.get_history(last_n)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
