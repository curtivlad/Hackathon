"""
simulation.py
Gestioneaza scenariile de simulare si ciclul de viata al agentilor.
Scenarii disponibile:
  1. blind_intersection  — doua vehicule vin din directii perpendiculare
  2. emergency_vehicle   — vehicul de urgenta vs vehicul normal
  3. multi_vehicle       — 4 vehicule simultan (stress test)
"""

import time
import threading
from typing import List, Optional
from agents import VehicleAgent
from infrastructure_agent import InfrastructureAgent
from v2x_channel import channel
from collision_detector import get_collision_pairs


class SimulationManager:
    """Gestioneaza pornirea, oprirea si starea simularii."""

    def __init__(self):
        self.infrastructure = InfrastructureAgent()
        self.vehicles: List[VehicleAgent] = []
        self.active_scenario: Optional[str] = None
        self.running = False
        self.stats = {
            "collisions_prevented": 0,
            "total_vehicles": 0,
            "elapsed_time": 0.0,
        }
        self._start_time = None
        self._monitor_thread = None

    # ------------------------------------------------------------------ #
    #  Scenarii                                                            #
    # ------------------------------------------------------------------ #

    def scenario_blind_intersection(self):
        """
        Scenariu 1: Intersectie cu vizibilitate redusa.
        Vehicul A vine din Nord spre Sud.
        Vehicul B vine din Est spre Vest.
        Fara cooperare -> coliziune. Cu cooperare -> B cedeaza.
        """
        self._clear_vehicles()

        vehicle_a = VehicleAgent(
            agent_id="VH_A",
            start_x=0.0,
            start_y=120.0,    # Nord
            direction=180.0,  # spre Sud
            initial_speed=11.0,
            target_speed=11.0,
            intention="straight",
        )

        vehicle_b = VehicleAgent(
            agent_id="VH_B",
            start_x=120.0,
            start_y=0.0,     # Est
            direction=270.0, # spre Vest
            initial_speed=10.0,
            target_speed=10.0,
            intention="straight",
        )

        self.vehicles = [vehicle_a, vehicle_b]
        self.active_scenario = "blind_intersection"

    def scenario_emergency_vehicle(self):
        """
        Scenariu 2: Vehicul de urgenta (ambulanta) vs vehicul normal.
        Ambulanta vine din Vest, vehiculul normal din Sud.
        Ambulanta are prioritate absoluta.
        """
        self._clear_vehicles()

        ambulance = VehicleAgent(
            agent_id="AMBULANCE",
            start_x=-120.0,
            start_y=0.0,
            direction=90.0,   # spre Est
            initial_speed=14.0,
            target_speed=14.0,
            intention="straight",
            is_emergency=True,
        )

        normal_car = VehicleAgent(
            agent_id="VH_C",
            start_x=0.0,
            start_y=-120.0,
            direction=0.0,    # spre Nord
            initial_speed=10.0,
            target_speed=10.0,
            intention="straight",
        )

        self.vehicles = [ambulance, normal_car]
        self.active_scenario = "emergency_vehicle"

    def scenario_multi_vehicle(self):
        """
        Scenariu 3: 4 vehicule simultan — toate directiile.
        """
        self._clear_vehicles()

        configs = [
            ("VH_N", 0.0,    120.0,  180.0, 10.0, "straight"),   # Nord -> Sud
            ("VH_S", 0.0,   -120.0,    0.0,  9.0, "straight"),   # Sud -> Nord
            ("VH_E", 120.0,    0.0,  270.0, 11.0, "straight"),   # Est -> Vest
            ("VH_W",-120.0,    0.0,   90.0,  8.0, "straight"),   # Vest -> Est
        ]

        self.vehicles = [
            VehicleAgent(
                agent_id=cid, start_x=sx, start_y=sy,
                direction=d, initial_speed=sp, intention=intent
            )
            for cid, sx, sy, d, sp, intent in configs
        ]
        self.active_scenario = "multi_vehicle"

    # ------------------------------------------------------------------ #
    #  Control simulare                                                    #
    # ------------------------------------------------------------------ #

    def start(self, scenario: str = "blind_intersection"):
        """Porneste simularea cu scenariul ales."""
        if self.running:
            self.stop()
            time.sleep(0.3)

        # Alege scenariul
        if scenario == "blind_intersection":
            self.scenario_blind_intersection()
        elif scenario == "emergency_vehicle":
            self.scenario_emergency_vehicle()
        elif scenario == "multi_vehicle":
            self.scenario_multi_vehicle()
        else:
            self.scenario_blind_intersection()

        self.running = True
        self._start_time = time.time()
        self.stats["total_vehicles"] += len(self.vehicles)

        # Porneste infrastructura
        self.infrastructure.start()

        # Porneste vehiculele
        for vehicle in self.vehicles:
            vehicle.start()

        # Porneste monitorizarea
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """Opreste simularea."""
        self.running = False
        for vehicle in self.vehicles:
            vehicle.stop()
        self.infrastructure.stop()

        # Curata canalul
        for v in self.vehicles:
            channel.remove_agent(v.agent_id)
        channel.remove_agent(self.infrastructure.agent_id)

    def restart(self, scenario: Optional[str] = None):
        """Reporneste scenariul curent sau unul nou."""
        sc = scenario or self.active_scenario or "blind_intersection"
        self.stop()
        time.sleep(0.3)
        self.start(sc)

    def _clear_vehicles(self):
        """Opreste si sterge vehiculele existente."""
        for v in self.vehicles:
            v.stop()
            channel.remove_agent(v.agent_id)
        self.vehicles = []

    def _monitor_loop(self):
        """Monitorizeaza coliziunile prevenite."""
        prev_risks = set()

        while self.running:
            all_states = channel.get_all_states()
            pairs = get_collision_pairs(all_states)

            current_risks = {(p["agent1"], p["agent2"]) for p in pairs if p["risk"] == "collision"}

            # Daca o pereche cu risc de coliziune a disparut (a fost evitata)
            for pair in prev_risks:
                if pair not in current_risks:
                    self.stats["collisions_prevented"] += 1

            prev_risks = current_risks

            if self._start_time:
                self.stats["elapsed_time"] = round(time.time() - self._start_time, 1)

            time.sleep(0.5)

    # ------------------------------------------------------------------ #
    #  Stare pentru frontend                                              #
    # ------------------------------------------------------------------ #

    def get_full_state(self) -> dict:
        """Returneaza starea completa a simularii pentru WebSocket."""
        all_agents = channel.to_dict()
        collision_pairs = get_collision_pairs(channel.get_all_states())

        return {
            "scenario": self.active_scenario,
            "running": self.running,
            "agents": all_agents,
            "infrastructure": self.infrastructure.get_state(),
            "collision_pairs": collision_pairs,
            "stats": self.stats,
            "timestamp": time.time(),
        }


# Instanta globala
simulation = SimulationManager()