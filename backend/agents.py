"""
agents.py — VehicleAgent cu oprire la linia de stop.
"""

import math
import time
import threading
from v2x_channel import V2XMessage, channel
from collision_detector import compute_risk_for_agent, distance, INTERSECTION_CENTER
from priority_negotiation import compute_decisions_for_all, compute_recommended_speed

MAX_SPEED = 14.0
ACCELERATION = 2.0
DECELERATION = 6.0
UPDATE_INTERVAL = 0.1
STOP_LINE = 35.0


class VehicleAgent:

    def __init__(self, agent_id, start_x, start_y, direction,
                 initial_speed=10.0, intention="straight",
                 is_emergency=False, target_speed=10.0):
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
        self._entered_intersection = False

    def _moves_on_y(self):
        rad = math.radians(self.direction)
        return abs(math.cos(rad)) >= abs(math.sin(rad))

    def _approaching_intersection(self):
        if self._moves_on_y():
            return abs(self.y) >= STOP_LINE
        else:
            return abs(self.x) >= STOP_LINE

    def _update_position(self):
        if self.speed < 0.01:
            return

        rad = math.radians(self.direction)
        new_x = self.x + self.speed * math.sin(rad) * UPDATE_INTERVAL
        new_y = self.y + self.speed * math.cos(rad) * UPDATE_INTERVAL

        if self.decision != "go" and not self.is_emergency and not self._entered_intersection:
            if self._moves_on_y():
                if abs(self.y) >= STOP_LINE and abs(new_y) < STOP_LINE:
                    new_y = STOP_LINE if self.y > 0 else -STOP_LINE
                    self.speed = 0.0
            else:
                if abs(self.x) >= STOP_LINE and abs(new_x) < STOP_LINE:
                    new_x = STOP_LINE if self.x > 0 else -STOP_LINE
                    self.speed = 0.0

        self.x = new_x
        self.y = new_y

        if self._moves_on_y():
            if abs(self.y) < STOP_LINE:
                self._entered_intersection = True
        else:
            if abs(self.x) < STOP_LINE:
                self._entered_intersection = True

    def _adjust_speed(self):
        if self.speed < self.recommended_speed:
            self.speed = min(self.speed + ACCELERATION * UPDATE_INTERVAL, self.recommended_speed)
        elif self.speed > self.recommended_speed:
            self.speed = max(self.speed - DECELERATION * UPDATE_INTERVAL, self.recommended_speed)

    def _get_movement_axis(self):
        rad = math.radians(self.direction)
        return "NS" if abs(math.cos(rad)) >= abs(math.sin(rad)) else "EW"

    def _is_red_light(self):
        all_states = channel.get_all_states()
        for msg in all_states.values():
            if msg.agent_type == "infrastructure":
                green_axis = "NS" if "NS" in msg.intention else "EW"
                return self._get_movement_axis() != green_axis
        return None

    def _make_decision(self):
        others = channel.get_other_agents(self.agent_id)
        all_agents = channel.get_all_states()

        self.risk_level = compute_risk_for_agent(
            channel.get_agent_state(self.agent_id) or self._build_message(),
            others
        )

        if all_agents:
            decisions = compute_decisions_for_all(all_agents)
            my = decisions.get(self.agent_id, {"decision": "go", "reason": "clear"})
            self.decision = my["decision"]
            self.reason = my["reason"]
        else:
            self.decision = "go"
            self.reason = "no_traffic"

        red = self._is_red_light()

        if red is True and not self._entered_intersection and not self.is_emergency:
            self.decision = "stop"
            self.reason = "red_light"
            if self._moves_on_y():
                dist = abs(self.y) - STOP_LINE
            else:
                dist = abs(self.x) - STOP_LINE
            if dist < 1.0:
                self.recommended_speed = 0.0
            elif dist < 20.0:
                self.recommended_speed = max(1.5, self.target_speed * (dist / 20.0))
            else:
                self.recommended_speed = self.target_speed
            return

        if red is False:
            self.decision = "go"
            self.reason = "green_light"
            self.recommended_speed = self.target_speed
            return

        msg = self._build_message()
        self.recommended_speed = compute_recommended_speed(msg, self.decision, self.target_speed)

        if self.is_emergency:
            self.decision = "go"
            self.recommended_speed = MAX_SPEED

        if self._entered_intersection:
            self.decision = "go"
            self.recommended_speed = self.target_speed

    def _build_message(self):
        return V2XMessage(
            agent_id=self.agent_id, agent_type="vehicle",
            x=self.x, y=self.y, speed=self.speed,
            direction=self.direction, intention=self.intention,
            risk_level=self.risk_level, decision=self.decision,
            is_emergency=self.is_emergency,
        )

    def _check_passed_intersection(self):
        dist = distance(self.x, self.y, *INTERSECTION_CENTER)
        if dist < 15.0:
            self._passed_intersection = True
        return self._passed_intersection and dist > 120.0

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
        self._entered_intersection = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_state(self):
        return {
            "agent_id": self.agent_id, "agent_type": "vehicle",
            "x": round(self.x, 2), "y": round(self.y, 2),
            "speed": round(self.speed, 2), "direction": self.direction,
            "intention": self.intention, "risk_level": self.risk_level,
            "decision": self.decision, "reason": self.reason,
            "is_emergency": self.is_emergency,
        }

