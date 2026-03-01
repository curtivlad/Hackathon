
import time
import threading
from typing import List, Optional
from agents import VehicleAgent
from infrastructure_agent import InfrastructureAgent
from v2x_channel import channel
from collision_detector import get_collision_pairs
from background_traffic import bg_traffic, get_grid_info
from telemetry import telemetry

LANE_OFFSET = 10.0


class SimulationManager:

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
        self._use_traffic_light = False


    def scenario_emergency_vehicle(self):
        self._clear_vehicles()
        ambulance = VehicleAgent(
            agent_id="AMBULANCE",
            start_x=-120.0,
            start_y=-LANE_OFFSET,
            direction=90.0,
            initial_speed=25.2,
            target_speed=25.2,
            intention="straight",
            is_emergency=True,
        )
        normal_car = VehicleAgent(
            agent_id="VH_C",
            start_x=LANE_OFFSET,
            start_y=-120.0,
            direction=0.0,
            initial_speed=18.0,
            target_speed=18.0,
            intention="straight",
        )
        self.vehicles = [ambulance, normal_car]
        self.active_scenario = "emergency_vehicle"

    def scenario_right_of_way(self):
        self._clear_vehicles()
        configs = [
            ("VH_N", -LANE_OFFSET,  120.0, 180.0, 18.0, "straight"),
            ("VH_E",  120.0,  LANE_OFFSET, 270.0, 18.0, "straight"),
            ("VH_S",  LANE_OFFSET, -120.0,   0.0, 18.0, "straight"),
        ]
        self.vehicles = [
            VehicleAgent(
                agent_id=cid, start_x=sx, start_y=sy,
                direction=d, initial_speed=sp, intention=intent
            )
            for cid, sx, sy, d, sp, intent in configs
        ]
        self.active_scenario = "right_of_way"


    def scenario_multi_vehicle_traffic_light(self):
        self._clear_vehicles()
        configs = [
            ("VH_N", -LANE_OFFSET,  120.0, 180.0, 18.0, "straight"),
            ("VH_S",  LANE_OFFSET, -120.0,   0.0, 16.2, "straight"),
            ("VH_E",  120.0,  LANE_OFFSET, 270.0, 19.8, "straight"),
            ("VH_W", -120.0, -LANE_OFFSET,  90.0, 14.4, "straight"),
        ]
        self.vehicles = [
            VehicleAgent(
                agent_id=cid, start_x=sx, start_y=sy,
                direction=d, initial_speed=sp, intention=intent
            )
            for cid, sx, sy, d, sp, intent in configs
        ]
        self.active_scenario = "multi_vehicle_traffic_light"

    def scenario_emergency_vehicle_no_lights(self):
        self._clear_vehicles()
        ambulance = VehicleAgent(
            agent_id="AMBULANCE",
            start_x=-120.0,
            start_y=-LANE_OFFSET,
            direction=90.0,
            initial_speed=25.2,
            target_speed=25.2,
            intention="straight",
            is_emergency=True,
        )
        normal_car = VehicleAgent(
            agent_id="VH_C",
            start_x=LANE_OFFSET,
            start_y=-120.0,
            direction=0.0,
            initial_speed=18.0,
            target_speed=18.0,
            intention="straight",
        )
        self.vehicles = [ambulance, normal_car]
        self.active_scenario = "emergency_vehicle_no_lights"

    def scenario_drunk_driver(self):
        self._clear_vehicles()
        normal = VehicleAgent(
            agent_id="VH_A",
            start_x=-LANE_OFFSET,
            start_y=120.0,
            direction=180.0,
            initial_speed=18.0,
            target_speed=18.0,
            intention="straight",
        )
        drunk = VehicleAgent(
            agent_id="DRUNK",
            start_x=120.0,
            start_y=LANE_OFFSET,
            direction=270.0,
            initial_speed=14.0,
            target_speed=14.0,
            intention="straight",
            is_drunk=True,
        )
        self.vehicles = [normal, drunk]
        self.active_scenario = "drunk_driver"

    def start(self, scenario: str = "right_of_way"):
        if self.running:
            self.stop()
            time.sleep(0.3)

        scenarios = {
            "emergency_vehicle": self.scenario_emergency_vehicle,
            "emergency_vehicle_no_lights": self.scenario_emergency_vehicle_no_lights,
            "right_of_way": self.scenario_right_of_way,
            "multi_vehicle_traffic_light": self.scenario_multi_vehicle_traffic_light,
            "drunk_driver": self.scenario_drunk_driver,
        }
        scenarios.get(scenario, self.scenario_right_of_way)()

        self.running = True
        self._start_time = time.time()
        self.stats["total_vehicles"] += len(self.vehicles)

        telemetry.record_scenario_start(scenario)
        telemetry.record_event("scenario_started", {"scenario": scenario, "vehicles": len(self.vehicles)})

        self._use_traffic_light = scenario in ("emergency_vehicle", "multi_vehicle_traffic_light")
        if self._use_traffic_light:
            self.infrastructure = InfrastructureAgent()
            self.infrastructure.start()
        for vehicle in self.vehicles:
            vehicle.start()

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        self.running = False
        telemetry.record_scenario_end()
        for vehicle in self.vehicles:
            vehicle.stop()
        if self._use_traffic_light:
            self.infrastructure.stop()
        for v in self.vehicles:
            channel.remove_agent(v.agent_id)
        if self._use_traffic_light:
            channel.remove_agent(self.infrastructure.agent_id)

    def restart(self, scenario: Optional[str] = None):
        sc = scenario or self.active_scenario or "right_of_way"
        self.stop()
        time.sleep(0.3)
        self.start(sc)

    def _clear_vehicles(self):
        for v in self.vehicles:
            v.stop()
            channel.remove_agent(v.agent_id)
        self.vehicles = []

    def _monitor_loop(self):
        prev_risks = set()
        while self.running:
            all_states = channel.get_all_states()
            pairs = get_collision_pairs(all_states)
            current_risks = {(p["agent1"], p["agent2"]) for p in pairs if p["risk"] == "collision"}
            for pair in prev_risks:
                if pair not in current_risks:
                    self.stats["collisions_prevented"] += 1
                    telemetry.record_event("collision_prevented", {
                        "agents": list(pair),
                    })
            prev_risks = current_risks

            for p in pairs:
                if p["risk"] in ("high", "collision"):
                    telemetry.record_event("risk_detected", {
                        "level": p["risk"],
                        "agents": [p["agent1"], p["agent2"]],
                        "ttc": p["ttc"],
                    })
            if self._start_time:
                self.stats["elapsed_time"] = round(time.time() - self._start_time, 1)

            stale = channel.cleanup_stale_agents()
            if stale:
                for v in self.vehicles:
                    if v.agent_id in stale and v._running:
                        v.stop()
                        self.stats.setdefault("stale_agents_removed", 0)
                        self.stats["stale_agents_removed"] += 1

            time.sleep(0.5)

    def get_full_state(self) -> dict:
        all_agents = channel.to_dict()
        all_collision_pairs = get_collision_pairs(channel.get_all_states())
        collision_pairs = [
            p for p in all_collision_pairs
            if not (p["agent1"].startswith("BG_") and p["agent2"].startswith("BG_"))
            and not (p["agent1"].startswith("AMBULANCE_") and p["agent2"].startswith("AMBULANCE_"))
        ]
        use_tl = self._use_traffic_light
        return {
            "scenario": self.active_scenario,
            "running": self.running,
            "agents": all_agents,
            "infrastructure": self.infrastructure.get_state() if use_tl else {},
            "collision_pairs": collision_pairs,
            "stats": self.stats,
            "timestamp": time.time(),
            "grid": get_grid_info(),
            "background_traffic": bg_traffic.active,
            "traffic_light_intersections": bg_traffic.get_traffic_light_states(),
        }


simulation = SimulationManager()
