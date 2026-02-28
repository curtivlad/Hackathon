"""
agents.py — Agentii AI: VehicleAgent si InfrastructureAgent (legacy).
"""

import math
import time
import threading
from v2x_channel import V2XMessage, channel
from collision_detector import compute_risk_for_agent, distance, INTERSECTION_CENTER
from priority_negotiation import compute_decisions_for_all, compute_recommended_speed

VEHICLE_LENGTH = 4.5
MAX_SPEED = 14.0
MIN_SPEED = 0.0
ACCELERATION = 2.0
DECELERATION = 4.0
UPDATE_INTERVAL = 0.1


class VehicleAgent:

    def __init__(self, agent_id: str, start_x: float, start_y: float,
                 direction: float, initial_speed: float = 10.0,
                 intention: str = "straight", is_emergency: bool = False,
                 target_speed: float = 10.0):
        self.agent_id = agent_id
        self.x = start_x
        self.y = start_y
        self.direction = direction
        self.speed = initial_speed
        self.target_speed = target_speed
        self.intention = intention
        self.is_emergency = is_emergency

        self.decision = "go"
        self.risk_level = "low"
        self.reason = "clear"
        self.recommended_speed = initial_speed

        self._running = False
        self._thread = None
        self._passed_intersection = False

    def _update_position(self):
        rad = math.radians(self.direction)
        self.x += self.speed * math.sin(rad) * UPDATE_INTERVAL
        self.y += self.speed * math.cos(rad) * UPDATE_INTERVAL

    def _adjust_speed(self):
        if self.speed < self.recommended_speed:
            self.speed = min(self.speed + ACCELERATION * UPDATE_INTERVAL, self.recommended_speed)
        elif self.speed > self.recommended_speed:
            self.speed = max(self.speed - DECELERATION * UPDATE_INTERVAL, self.recommended_speed)

    def _make_decision(self):
        others = channel.get_other_agents(self.agent_id)
        all_agents = channel.get_all_states()

        self.risk_level = compute_risk_for_agent(
            channel.get_agent_state(self.agent_id) or self._build_message(),
            others
        )

        if all_agents:
            decisions = compute_decisions_for_all(all_agents)
            my_decision = decisions.get(self.agent_id, {"decision": "go", "reason": "clear"})
            self.decision = my_decision["decision"]
            self.reason = my_decision["reason"]
        else:
            self.decision = "go"
            self.reason = "no_traffic"

        msg = self._build_message()
        self.recommended_speed = compute_recommended_speed(msg, self.decision, self.target_speed)

        if self.is_emergency:
            self.decision = "go"
            self.recommended_speed = MAX_SPEED

    def _build_message(self) -> V2XMessage:
        return V2XMessage(
            agent_id=self.agent_id,
            agent_type="vehicle",
            x=self.x,
            y=self.y,
            speed=self.speed,
            direction=self.direction,
            intention=self.intention,
            risk_level=self.risk_level,
            decision=self.decision,
            is_emergency=self.is_emergency,
        )

    def _check_passed_intersection(self):
        dist = distance(self.x, self.y, *INTERSECTION_CENTER)
        if dist < 15.0:
            self._passed_intersection = True
        if self._passed_intersection and dist > 120.0:
            return True
        return False

    def _run_loop(self):
        while self._running:
            self._make_decision()
            self._adjust_speed()
            self._update_position()
            channel.publish(self._build_message())
            if self._check_passed_intersection():
                self.stop()
                channel.remove_agent(self.agent_id)
                break
            time.sleep(UPDATE_INTERVAL)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_state(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": "vehicle",
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "speed": round(self.speed, 2),
            "direction": self.direction,
            "intention": self.intention,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "is_emergency": self.is_emergency,
        }

