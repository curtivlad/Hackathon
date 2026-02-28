"""
agents.py — VehicleAgent cu AI LLM brain + MEMORIE PROPRIE,
            perceptie V2X (broadcast alerts), oprire corecta la semafor,
            reluare la verde, si circulatie pe banda din dreapta (Europa).

Cerinte indeplinite:
- Memorie proprie per agent (prin LLMBrain.memory)
- Perceptie prin mesaje V2X (broadcast alerts + stari alti agenti)
- Decizii autonome non-deterministe (memoria + V2X variaza la fiecare pas)
- Nu executa instructiuni fixe identice (fallback adaptiv bazat pe memorie)
"""

import math
import time
import random
import threading
import logging
from v2x_channel import V2XMessage, V2XBroadcast, channel
from collision_detector import (
    compute_risk_for_agent, distance, INTERSECTION_CENTER,
    compute_ttc, get_velocity_components
)
from priority_negotiation import compute_decisions_for_all, compute_recommended_speed
from llm_brain import LLMBrain, LLM_ENABLED

logger = logging.getLogger("agents")

MAX_SPEED = 25.0
ACCELERATION = 4.0
DECELERATION = 10.0
UPDATE_INTERVAL = 0.05
STOP_LINE = 35.0

# Drunk driver erratic behavior parameters
DRUNK_SWERVE_MAX = 12.0        # max swerve angle in degrees
DRUNK_SWERVE_PERIOD = 1.5      # seconds per swerve oscillation
DRUNK_RANDOM_STOP_CHANCE = 0.005   # per tick chance to randomly stop
DRUNK_RANDOM_ACCEL_CHANCE = 0.02   # per tick chance to randomly accelerate
DRUNK_IGNORE_RED_CHANCE = 0.7      # chance to ignore red light
DRUNK_RANDOM_BRAKE_CHANCE = 0.01   # per tick chance to randomly brake hard
DRUNK_SPEED_VARIANCE = 5.0        # random speed variation


class VehicleAgent:

    def __init__(self, agent_id, start_x, start_y, direction,
                 initial_speed=10.0, intention="straight",
                 is_emergency=False, target_speed=10.0,
                 waypoints=None, is_drunk=False, persistent=False):
        self.agent_id = agent_id
        self.x = start_x
        self.y = start_y
        self.direction = direction
        self.speed = initial_speed
        self.target_speed = target_speed
        self.intention = intention
        self.is_emergency = is_emergency
        self.is_drunk = is_drunk
        self.persistent = persistent   # never despawn — turn at edges
        if self.is_emergency:
            self.target_speed = MAX_SPEED
        self.decision = "go"
        self.risk_level = "low"
        self.reason = "clear"
        self.recommended_speed = MAX_SPEED if self.is_emergency else initial_speed
        self._running = False
        self._thread = None
        self._passed_intersection = False
        self._entered_intersection = False

        # Waypoint-based routing for background traffic
        self._waypoints = list(waypoints) if waypoints else None
        self._is_background = waypoints is not None

        # LLM Brain cu MEMORIE PROPRIE — fiecare masina are propriul "creier" AI
        self._llm_brain = LLMBrain(agent_id)

        # Fallback memory (pentru cand LLM nu e disponibil)
        self._fallback_history = []
        self._fallback_consecutive = 0
        self._fallback_last_action = None

        self._drunk_phase = random.uniform(0, 2 * math.pi)
        self._drunk_next_erratic = time.time() + random.uniform(3.0, 6.0)
        self._drunk_erratic_end = 0.0
        self._drunk_erratic_speed = 0.0

    # ──────────────────────── Helpers ────────────────────────

    def _moves_on_y(self):
        rad = math.radians(self.direction)
        return abs(math.cos(rad)) >= abs(math.sin(rad))

    def _get_movement_axis(self):
        rad = math.radians(self.direction)
        return "NS" if abs(math.cos(rad)) >= abs(math.sin(rad)) else "EW"

    def _distance_to_stop_line(self):
        """Distanta pana la linia de stop pe axa de miscare."""
        if self._moves_on_y():
            return max(0.0, abs(self.y) - STOP_LINE)
        else:
            return max(0.0, abs(self.x) - STOP_LINE)

    def _approaching_intersection(self):
        if self._moves_on_y():
            return abs(self.y) >= STOP_LINE
        else:
            return abs(self.x) >= STOP_LINE

    # ──────────────────────── Traffic Light Detection ────────────────────────

    def _is_red_light(self):
        """Returneaza True daca semaforul e rosu, False daca e verde, None daca nu exista semafor."""
        all_states = channel.get_all_states()
        for msg in all_states.values():
            if msg.agent_type == "infrastructure":
                green_axis = "NS" if "NS" in msg.intention else "EW"
                my_axis = self._get_movement_axis()
                return my_axis != green_axis
        return None  # nu exista semafor

    def _get_traffic_light_str(self):
        """Returneaza 'green', 'red', sau None."""
        red = self._is_red_light()
        if red is True:
            return "red"
        elif red is False:
            return "green"
        return None

    # ──────────────────────── V2X Broadcast ────────────────────────

    def _broadcast_v2x_alert(self, alert_type: str, message: str, target_id=None):
        """Trimite o alerta V2X catre ceilalti agenti."""
        alert = V2XBroadcast(
            from_id=self.agent_id,
            alert_type=alert_type,
            message=message,
            target_id=target_id,
        )
        channel.broadcast(alert)

    def _get_v2x_broadcasts_text(self) -> str:
        """Obtine alertele V2X primite si le formateaza ca text pentru prompt."""
        alerts = channel.get_broadcasts_for(self.agent_id, last_seconds=5.0)
        if not alerts:
            return ""
        lines = ["V2X BROADCAST MESSAGES RECEIVED:"]
        for a in alerts[-5:]:  # ultimele 5
            lines.append(f"  - From {a.from_id}: [{a.alert_type}] {a.message}")

        # Inregistreaza in memoria agentului
        for a in alerts[-3:]:
            self._llm_brain.memory.record_v2x_alert(a.from_id, a.alert_type, a.message)

        return "\n".join(lines)

    # ──────────────────────── Nearby vehicles for LLM ────────────────────────

    def _get_nearby_vehicles_info(self):
        """Construieste lista cu informatii despre vehiculele din jur pentru LLM."""
        others = channel.get_other_agents(self.agent_id)
        my_msg = self._build_message()
        result = []
        for agent_id, msg in others.items():
            if msg.agent_type != "vehicle":
                continue
            dist = distance(self.x, self.y, msg.x, msg.y)
            if dist > 200:  # prea departe, nu conteaza
                continue
            ttc = compute_ttc(my_msg, msg)
            ttc_str = f"{ttc:.1f}s" if ttc < 999 else "inf"
            result.append({
                "id": msg.agent_id,
                "x": msg.x,
                "y": msg.y,
                "speed": msg.speed,
                "direction": msg.direction,
                "intention": msg.intention,
                "is_emergency": msg.is_emergency,
                "is_drunk": msg.is_drunk,
                "dist": dist,
                "ttc": ttc_str,
                "decision": msg.decision,  # ce decizie a luat celalalt agent
            })
        return result

    # ──────────────────────── Emergency rear-collision avoidance ────────────────────────

    def _emergency_rear_collision_speed(self):
        nearby = self._get_nearby_vehicles_info()
        rad = math.radians(self.direction)
        dx_fwd = math.sin(rad)
        dy_fwd = math.cos(rad)
        for o in nearby:
            rel_x = o["x"] - self.x
            rel_y = o["y"] - self.y
            proj = rel_x * dx_fwd + rel_y * dy_fwd
            if proj < 0 or proj > 30:
                continue
            perp = abs(rel_x * (-dy_fwd) + rel_y * dx_fwd)
            if perp > 8:
                continue
            dir_diff = abs(((o["direction"] - self.direction + 180) % 360) - 180)
            if dir_diff > 45:
                continue
            if o["speed"] < self.speed * 0.5:
                gap = proj
                safe_margin = 5.0
                stopping_dist = max(0, gap - safe_margin)
                if stopping_dist < 0.5:
                    return max(o["speed"], 0.0)
                v_safe = math.sqrt(max(0, o["speed"] ** 2 + 2 * DECELERATION * stopping_dist))
                return min(v_safe, MAX_SPEED)
        return MAX_SPEED

    # ──────────────────────── Decision Making (LLM + Adaptive Fallback) ────────────────────────

    def _make_decision(self):
        """
        Logica de decizie:
        1. Daca e sofer beat — comportament erratic (ignora reguli)
        2. Incearca LLM (daca e activat si API key valid) — include memorie + V2X
        3. Fallback ADAPTIV bazat pe memorie daca LLM nu e disponibil
        """
        others = channel.get_other_agents(self.agent_id)

        # Compute risk
        self.risk_level = compute_risk_for_agent(
            channel.get_agent_state(self.agent_id) or self._build_message(),
            others
        )

        # Broadcast V2X alerts based on current state
        self._send_situational_v2x_alerts()

        if self.is_emergency:
            self.decision = "go"
            self.reason = "emergency_override"
            self.recommended_speed = self._emergency_rear_collision_speed()
            self._fallback_consecutive = 0
            self._fallback_last_action = None
            return

        # ── Drunk driver: erratic behavior ──
        if self.is_drunk:
            self._make_decision_drunk()
            return

        # ── Try LLM first ──
        if LLM_ENABLED:
            traffic_light = self._get_traffic_light_str()
            nearby = self._get_nearby_vehicles_info()
            dist_to_stop = self._distance_to_stop_line()
            v2x_text = self._get_v2x_broadcasts_text()

            llm_result = self._llm_brain.decide(
                x=self.x, y=self.y,
                speed=self.speed,
                direction=self.direction,
                intention=self.intention,
                is_emergency=self.is_emergency,
                entered_intersection=self._entered_intersection,
                traffic_light=traffic_light,
                others=nearby,
                risk_level=self.risk_level,
                distance_to_stop_line=dist_to_stop,
                v2x_broadcasts=v2x_text,
            )

            if llm_result is not None:
                self.decision = llm_result["action"]
                self.reason = llm_result["reason"]
                self.recommended_speed = llm_result["speed"]

                # LLM a decis — resetam contorul fallback (nu mai suntem in fallback)
                self._fallback_consecutive = 0
                self._fallback_last_action = None

                # Safety overrides — LLM nu poate trece pe rosu
                if not self.is_emergency and not self._entered_intersection:
                    if traffic_light == "red":
                        self.decision = "stop"
                        self.reason = "red_light"
                        if dist_to_stop < 1.0:
                            self.recommended_speed = 0.0
                        elif dist_to_stop < 20.0:
                            self.recommended_speed = min(
                                self.recommended_speed,
                                max(1.5, self.target_speed * (dist_to_stop / 20.0))
                            )

                # Daca e deja in intersectie, nu te opri
                if self._entered_intersection:
                    self.decision = "go"
                    self.recommended_speed = max(self.recommended_speed, self.target_speed * 0.5)

                return

        # ── Fallback: reguli ADAPTIVE (nu fixe) ──
        self._make_decision_adaptive_fallback()

    def _send_situational_v2x_alerts(self):
        """Trimite alerte V2X in functie de situatia curenta."""
        # Emergency broadcast
        if self.is_emergency:
            self._broadcast_v2x_alert(
                "emergency",
                f"Emergency vehicle approaching at speed {self.speed:.0f}m/s heading {self.direction}°"
            )

        # Drunk driver broadcast — warn others about erratic behavior
        if self.is_drunk:
            self._broadcast_v2x_alert(
                "erratic_driving",
                f"DRUNK DRIVER! Erratic vehicle at ({self.x:.0f},{self.y:.0f}) speed {self.speed:.0f}m/s heading {self.direction:.0f}°"
            )

        # Braking alert
        if self.decision in ("brake", "stop") and self.speed > 2.0:
            self._broadcast_v2x_alert(
                "braking",
                f"Braking hard at ({self.x:.0f},{self.y:.0f}), speed dropping"
            )

        # Entering intersection alert
        if self._entered_intersection and self.speed > 0.5:
            self._broadcast_v2x_alert(
                "entering_intersection",
                f"Inside intersection heading {self.direction}° at {self.speed:.0f}m/s"
            )

        # Near-miss warning — warn others when risk is high
        if self.risk_level in ("high", "collision"):
            self._broadcast_v2x_alert(
                "near_miss",
                f"High risk detected! I'm at ({self.x:.0f},{self.y:.0f}) risk={self.risk_level}"
            )

    def _make_decision_drunk(self):
        """
        Comportament ERRATIC — sofer beat.
        Ignora semafoare, accelereaza/franeaza aleator, face swerve.
        """
        # Swerve sinusoidal — oscilatie de directie
        t = time.time()
        swerve_angle = DRUNK_SWERVE_MAX * math.sin(2 * math.pi * t / DRUNK_SWERVE_PERIOD)
        # Add some random jitter
        swerve_angle += random.uniform(-3, 3)

        # Apply swerve to direction (but remember original for waypoint nav)
        if not hasattr(self, '_drunk_base_direction'):
            self._drunk_base_direction = self.direction
        # Slowly drift the base direction randomly
        self._drunk_base_direction += random.uniform(-0.5, 0.5)
        self.direction = (self._drunk_base_direction + swerve_angle) % 360

        # Random erratic actions
        roll = random.random()

        if roll < DRUNK_RANDOM_STOP_CHANCE:
            # Random stop for no reason
            self.decision = "stop"
            self.reason = "drunk_random_stop"
            self.recommended_speed = 0.0
            logger.info(f"[{self.agent_id}] DRUNK: stopped randomly!")
        elif roll < DRUNK_RANDOM_STOP_CHANCE + DRUNK_RANDOM_BRAKE_CHANCE:
            # Random hard brake
            self.decision = "brake"
            self.reason = "drunk_random_brake"
            self.recommended_speed = max(0.0, self.speed - random.uniform(3, 6))
            logger.info(f"[{self.agent_id}] DRUNK: braking randomly!")
        elif roll < DRUNK_RANDOM_STOP_CHANCE + DRUNK_RANDOM_BRAKE_CHANCE + DRUNK_RANDOM_ACCEL_CHANCE:
            # Random acceleration burst
            self.decision = "go"
            self.reason = "drunk_acceleration"
            self.recommended_speed = min(MAX_SPEED, self.target_speed + random.uniform(2, DRUNK_SPEED_VARIANCE))
            logger.info(f"[{self.agent_id}] DRUNK: accelerating erratically!")
        else:
            # "Normal" drunk driving — slightly erratic speed
            self.decision = "go"
            self.reason = "drunk_driving"
            self.recommended_speed = self.target_speed + random.uniform(-2, 3)
            self.recommended_speed = max(2.0, min(MAX_SPEED, self.recommended_speed))

        # Ignore red lights most of the time
        traffic_light = self._get_traffic_light_str()
        if traffic_light == "red" and not self._entered_intersection:
            if random.random() < DRUNK_IGNORE_RED_CHANCE:
                # Drunk driver IGNORES red light
                self.decision = "go"
                self.reason = "drunk_ignores_red"
                self.recommended_speed = max(self.recommended_speed, self.target_speed * 0.8)
                logger.warning(f"[{self.agent_id}] DRUNK: IGNORING RED LIGHT!")
            # else: occasionally they do stop at red (30% chance)

        # If in intersection, keep going (even drunk drivers usually continue)
        if self._entered_intersection:
            self.decision = "go"
            self.recommended_speed = max(self.recommended_speed, self.target_speed * 0.6)

    def _make_decision_adaptive_fallback(self):
        """
        Fallback ADAPTIV — nu pur deterministic.
        Tine cont de istoricul deciziilor si nu repeta identic la fiecare pas.
        """
        all_agents = channel.get_all_states()

        if all_agents:
            decisions = compute_decisions_for_all(all_agents)
            my = decisions.get(self.agent_id, {"decision": "go", "reason": "clear"})
            base_decision = my["decision"]
            base_reason = my["reason"]
        else:
            base_decision = "go"
            base_reason = "no_traffic"

        red = self._is_red_light()

        # ── RED: opreste-te inainte de linia de stop ──
        if red is True and not self._entered_intersection and not self.is_emergency:
            self.decision = "stop"
            self.reason = "red_light"
            dist = self._distance_to_stop_line()
            if dist < 1.0:
                self.recommended_speed = 0.0
            elif dist < 20.0:
                self.recommended_speed = max(1.5, self.target_speed * (dist / 20.0))
            else:
                self.recommended_speed = self.target_speed
            self._record_fallback_decision("stop", "red_light")
            return

        # ── GREEN: porneste si mergi! ──
        if red is False:
            self.decision = "go"
            self.reason = "green_light"
            self.recommended_speed = self.target_speed
            self._record_fallback_decision("go", "green_light")
            return

        # ── Fara semafor: prioritate de dreapta + ADAPTARE ──
        self.decision = base_decision
        self.reason = base_reason

        # ADAPTARE: daca am cedat prea mult timp si nu mai e risc, pleaca
        if self.decision in ("yield", "stop") and self._fallback_consecutive > 40:
            # Verifica daca e safe sa plec
            nearby = self._get_nearby_vehicles_info()
            all_safe = True
            for o in nearby:
                ttc_str = o.get("ttc", "inf")
                try:
                    ttc_val = float(ttc_str.replace("s", "")) if isinstance(ttc_str, str) else float(ttc_str)
                except (ValueError, AttributeError):
                    ttc_val = float("inf")
                if ttc_val < 5.0:
                    all_safe = False
                    break
            if all_safe:
                self.decision = "go"
                self.reason = "waited_long_enough"
                self._fallback_consecutive = 0
                self._fallback_last_action = None
                logger.info(f"[{self.agent_id}] Adaptive: stopped yielding after prolonged wait")

        # ADAPTARE: check V2X broadcasts for emergency nearby
        v2x_alerts = channel.get_broadcasts_for(self.agent_id, last_seconds=3.0)
        for alert in v2x_alerts:
            if alert.alert_type == "emergency":
                if self.decision == "go":
                    self.decision = "yield"
                    self.reason = "v2x_emergency_nearby"
                    break
            elif alert.alert_type == "erratic_driving":
                # Sofer beat detectat prin V2X — incetineste si cedeaza
                if self.decision == "go":
                    nearby = self._get_nearby_vehicles_info()
                    for o in nearby:
                        if o["id"] == alert.from_id:
                            ttc_str = o.get("ttc", "inf")
                            try:
                                ttc_val = float(ttc_str.replace("s", "")) if isinstance(ttc_str, str) else float(ttc_str)
                            except (ValueError, AttributeError):
                                ttc_val = float("inf")
                            if ttc_val < 8.0:
                                self.decision = "brake"
                                self.reason = "v2x_drunk_driver_nearby"
                                self.recommended_speed = max(0.0, self.speed * 0.3)
                                logger.info(f"[{self.agent_id}] Braking: drunk driver {alert.from_id} nearby!")
                            break
            elif alert.alert_type == "entering_intersection":
                # Alt vehicul e deja in intersectie
                if not self._entered_intersection and self.decision == "go":
                    nearby = self._get_nearby_vehicles_info()
                    for o in nearby:
                        if o["id"] == alert.from_id:
                            ttc_str = o.get("ttc", "inf")
                            try:
                                ttc_val = float(ttc_str.replace("s", "")) if isinstance(ttc_str, str) else float(ttc_str)
                            except (ValueError, AttributeError):
                                ttc_val = float("inf")
                            if ttc_val < 6.0:
                                self.decision = "yield"
                                self.reason = "v2x_vehicle_in_intersection"
                            break

        msg = self._build_message()
        self.recommended_speed = compute_recommended_speed(msg, self.decision, self.target_speed)

        if self._entered_intersection:
            self.decision = "go"
            self.recommended_speed = self.target_speed

        self._record_fallback_decision(self.decision, self.reason)

    def _record_fallback_decision(self, action: str, reason: str):
        """Inregistreaza decizia fallback in memoria proprie."""
        # Track consecutive same action (deterministic anti-deadlock)
        if action == self._fallback_last_action:
            self._fallback_consecutive += 1
        else:
            self._fallback_consecutive = 1  # prima aparitie a noii actiuni
        self._fallback_last_action = action

        # Record in LLM brain memory (chiar daca LLM nu e activ, memoria exista)
        situation = (
            f"pos=({self.x:.0f},{self.y:.0f}) spd={self.speed:.1f} "
            f"risk={self.risk_level} light={self._get_traffic_light_str() or 'none'} "
            f"mode=fallback"
        )
        self._llm_brain.memory.record_decision(situation, {
            "action": action,
            "speed": self.recommended_speed,
            "reason": reason,
        })

    # ──────────────────────── Position & Speed ────────────────────────

    def _update_position(self):
        if self.speed < 0.01:
            return

        rad = math.radians(self.direction)
        new_x = self.x + self.speed * math.sin(rad) * UPDATE_INTERVAL
        new_y = self.y + self.speed * math.cos(rad) * UPDATE_INTERVAL

        # Opreste-te la linia de stop daca nu ai voie sa treci
        if self.decision != "go" and not self.is_emergency and not self.is_drunk and not self._entered_intersection:
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

        # Detecteaza ca a intrat in intersectie
        if self._moves_on_y():
            if abs(self.y) < STOP_LINE:
                self._entered_intersection = True
        else:
            if abs(self.x) < STOP_LINE:
                self._entered_intersection = True

    def _adjust_speed(self):
        if self.is_drunk:
            now = time.time()
            self.recommended_speed += 4.0 * math.sin(now * 1.5 + self._drunk_phase)
            if now >= self._drunk_next_erratic:
                self._drunk_erratic_speed = random.choice([
                    random.uniform(2.0, 5.0),
                    random.uniform(MAX_SPEED * 0.9, MAX_SPEED),
                ])
                self._drunk_erratic_end = now + random.uniform(0.5, 1.5)
                self._drunk_next_erratic = self._drunk_erratic_end + random.uniform(3.0, 6.0)
            if now < self._drunk_erratic_end:
                self.recommended_speed = self._drunk_erratic_speed
            self.recommended_speed = max(0.0, min(self.recommended_speed, MAX_SPEED))
        if self.speed < self.recommended_speed:
            self.speed = min(self.speed + ACCELERATION * UPDATE_INTERVAL, self.recommended_speed)
        elif self.speed > self.recommended_speed:
            self.speed = max(self.speed - DECELERATION * UPDATE_INTERVAL, self.recommended_speed)
        if self.is_drunk:
            self.speed = max(0.0, min(self.speed, MAX_SPEED))

    # ──────────────────────── Message ────────────────────────

    def _build_message(self):
        return V2XMessage(
            agent_id=self.agent_id, agent_type="vehicle",
            x=self.x, y=self.y, speed=self.speed,
            direction=self.direction, intention=self.intention,
            risk_level=self.risk_level, decision=self.decision,
            is_emergency=self.is_emergency,
            is_drunk=self.is_drunk,
        )

    # ──────────────────────── Lifecycle ────────────────────────

    def _check_passed_intersection(self):
        dist = distance(self.x, self.y, *INTERSECTION_CENTER)
        if dist < 15.0:
            self._passed_intersection = True
        return self._passed_intersection and dist > 120.0

    # ──────────────────────── Waypoint Navigation (background traffic) ────────────────────────

    def _nearest_intersection(self):
        """Find the nearest intersection center from the grid."""
        from background_traffic import INTERSECTIONS
        best = None
        best_dist = float('inf')
        for ix, iy in INTERSECTIONS:
            d = distance(self.x, self.y, ix, iy)
            if d < best_dist:
                best_dist = d
                best = (ix, iy)
        return best, best_dist

    def _distance_to_nearest_stop_line(self):
        """Distance to the stop line of the nearest intersection."""
        inter, _ = self._nearest_intersection()
        if inter is None:
            return float('inf')
        ix, iy = inter
        if self._moves_on_y():
            return max(0.0, abs(self.y - iy) - STOP_LINE)
        else:
            return max(0.0, abs(self.x - ix) - STOP_LINE)

    def _is_inside_nearest_intersection(self):
        """Check if we're inside the nearest intersection box."""
        inter, _ = self._nearest_intersection()
        if inter is None:
            return False
        ix, iy = inter
        return abs(self.x - ix) < STOP_LINE and abs(self.y - iy) < STOP_LINE

    def _bg_compute_risk_and_decision(self):
        """Compute risk and decision for a background vehicle using V2X channel."""
        others = channel.get_other_agents(self.agent_id)
        my_msg = self._build_message()

        # Compute risk directly via TTC (skip compute_risk_for_agent which
        # filters by distance to INTERSECTION_CENTER at 0,0)
        self.risk_level = "low"
        for other_id, other_msg in others.items():
            if other_msg.agent_type != "vehicle":
                continue
            d = distance(self.x, self.y, other_msg.x, other_msg.y)
            if d > 150:
                continue
            # Skip same-road opposite direction (they won't collide)
            # Also verify they're on the same road (close perpendicular coord)
            my_axis = self._get_movement_axis()
            o_rad = math.radians(other_msg.direction)
            o_axis = "NS" if abs(math.cos(o_rad)) >= abs(math.sin(o_rad)) else "EW"
            if my_axis == o_axis:
                angle_diff = abs(self.direction - other_msg.direction) % 360
                if abs(angle_diff - 180) < 15:
                    perp_dist = abs(self.x - other_msg.x) if my_axis == "NS" else abs(self.y - other_msg.y)
                    if perp_dist < 25.0:
                        continue  # genuinely opposite directions on same road
            ttc = compute_ttc(my_msg, other_msg)
            if ttc < 3.0:
                self.risk_level = "collision"
                break
            elif ttc < 6.0 and self.risk_level != "collision":
                self.risk_level = "high"
            elif ttc < 10.0 and self.risk_level not in ("collision", "high"):
                self.risk_level = "medium"

        inside = self._is_inside_nearest_intersection()

        # If already inside intersection, keep going
        if inside:
            self.decision = "go"
            self.reason = "in_intersection"
            self.recommended_speed = self.target_speed
            return

        # ── Check grid traffic lights ──
        inter, inter_dist = self._nearest_intersection()
        if inter and inter_dist < 100:
            from background_traffic import bg_traffic
            tl = bg_traffic.get_traffic_light_for(inter[0], inter[1])
            if tl is not None:
                my_axis = self._get_movement_axis()
                if not tl.is_green_for_axis(my_axis) and not self.is_emergency:
                    dist_to_stop = self._distance_to_nearest_stop_line()
                    self.decision = "stop"
                    self.reason = "red_light"
                    if dist_to_stop < 1.0:
                        self.recommended_speed = 0.0
                    elif dist_to_stop < 25.0:
                        self.recommended_speed = max(1.0, self.target_speed * (dist_to_stop / 30.0))
                    else:
                        self.recommended_speed = self.target_speed * 0.6
                    return

        # Check for nearby vehicles that could collide
        dist_to_stop = self._distance_to_nearest_stop_line()
        dominated = False  # should I yield?

        for other_id, other_msg in others.items():
            if other_msg.agent_type != "vehicle":
                continue
            d = distance(self.x, self.y, other_msg.x, other_msg.y)
            if d > 150:
                continue

            # ── Same-lane, same-direction: follow the leader ──
            my_axis = self._get_movement_axis()
            o_rad = math.radians(other_msg.direction)
            o_axis = "NS" if abs(math.cos(o_rad)) >= abs(math.sin(o_rad)) else "EW"
            angle_diff = abs(self.direction - other_msg.direction) % 360
            same_dir = angle_diff < 30 or angle_diff > 330

            if my_axis == o_axis and same_dir and d < 80:
                # Check if other is AHEAD of us (dot product with our heading)
                rad = math.radians(self.direction)
                fwd_x = math.sin(rad)
                fwd_y = math.cos(rad)
                dx = other_msg.x - self.x
                dy = other_msg.y - self.y
                dot = fwd_x * dx + fwd_y * dy
                if dot > 0:  # other is ahead
                    # Follow: match speed, keep distance
                    safe_dist = 25.0
                    if d < safe_dist:
                        self.decision = "brake"
                        self.reason = "following"
                        self.recommended_speed = max(0.0, other_msg.speed * 0.7)
                    elif d < safe_dist * 2:
                        self.decision = "go"
                        self.reason = "following"
                        self.recommended_speed = min(self.target_speed, other_msg.speed)
                    else:
                        continue  # far enough, don't care
                    return  # handled — skip intersection logic

            ttc = compute_ttc(my_msg, other_msg)

            # Emergency vehicle nearby — always yield
            if other_msg.is_emergency and ttc < 10.0:
                dominated = True
                self.reason = "emergency_nearby"
                break

            # Drunk driver nearby — brake and yield
            if other_msg.is_drunk and ttc < 10.0:
                dominated = True
                self.reason = "drunk_driver_nearby"
                break

            # Very close and converging — check who yields
            if ttc < 5.0:
                # Simple priority: the one with lower agent_id goes first
                # (mimics priority negotiation without full logic)
                # Also: if other is already faster/closer to intersection, yield
                if other_msg.speed > self.speed + 1.0:
                    dominated = True
                    self.reason = "faster_vehicle"
                elif self.agent_id > other_msg.agent_id:
                    dominated = True
                    self.reason = "id_priority"
                break

            if ttc < 8.0 and self.risk_level in ("high", "collision"):
                # Check approach directions — if perpendicular, use right-of-way
                my_axis = self._get_movement_axis()
                other_rad = math.radians(other_msg.direction)
                other_axis = "NS" if abs(math.cos(other_rad)) >= abs(math.sin(other_rad)) else "EW"

                if my_axis != other_axis:
                    # Perpendicular — use right-hand rule based on heading
                    from priority_negotiation import is_on_right
                    # Determine approach direction from heading
                    def _heading_to_approach(direction):
                        d = direction % 360
                        if 315 <= d or d < 45:
                            return "south"   # heading north, coming from south
                        elif 45 <= d < 135:
                            return "west"    # heading east, coming from west
                        elif 135 <= d < 225:
                            return "north"   # heading south, coming from north
                        else:
                            return "east"    # heading west, coming from east

                    my_approach = _heading_to_approach(self.direction)
                    other_approach = _heading_to_approach(other_msg.direction)
                    if is_on_right(my_approach, other_approach):
                        dominated = True
                        self.reason = "right_of_way"
                        break

        if dominated:
            self.decision = "yield"
            if dist_to_stop < 1.0:
                self.recommended_speed = 0.0
            elif dist_to_stop < 30.0:
                self.recommended_speed = max(1.0, self.target_speed * (dist_to_stop / 40.0))
            else:
                self.recommended_speed = max(2.0, self.target_speed * 0.4)
        else:
            self.decision = "go"
            self.reason = "clear"
            self.recommended_speed = self.target_speed

    def _bg_drunk_erratic_decision(self):
        """Erratic decision making for drunk driver on the grid (waypoint-based)."""
        # Broadcast erratic driving alert via V2X
        self._broadcast_v2x_alert(
            "erratic_driving",
            f"DRUNK DRIVER! Erratic vehicle at ({self.x:.0f},{self.y:.0f}) speed {self.speed:.0f}m/s heading {self.direction:.0f}°"
        )

        # Check risk for V2X awareness (others can see us)
        others = channel.get_other_agents(self.agent_id)
        my_msg = self._build_message()
        self.risk_level = "low"
        for other_id, other_msg in others.items():
            if other_msg.agent_type != "vehicle":
                continue
            d = distance(self.x, self.y, other_msg.x, other_msg.y)
            if d > 150:
                continue
            ttc = compute_ttc(my_msg, other_msg)
            if ttc < 3.0:
                self.risk_level = "collision"
            elif ttc < 6.0 and self.risk_level != "collision":
                self.risk_level = "high"

        # Random erratic actions
        roll = random.random()

        if roll < DRUNK_RANDOM_STOP_CHANCE:
            self.decision = "stop"
            self.reason = "drunk_random_stop"
            self.recommended_speed = 0.0
        elif roll < DRUNK_RANDOM_STOP_CHANCE + DRUNK_RANDOM_BRAKE_CHANCE:
            self.decision = "brake"
            self.reason = "drunk_random_brake"
            self.recommended_speed = max(0.0, self.speed - random.uniform(3, 6))
        elif roll < DRUNK_RANDOM_STOP_CHANCE + DRUNK_RANDOM_BRAKE_CHANCE + DRUNK_RANDOM_ACCEL_CHANCE:
            self.decision = "go"
            self.reason = "drunk_acceleration"
            self.recommended_speed = min(MAX_SPEED, self.target_speed + random.uniform(2, DRUNK_SPEED_VARIANCE))
        else:
            self.decision = "go"
            self.reason = "drunk_driving"
            self.recommended_speed = self.target_speed + random.uniform(-2, 3)
            self.recommended_speed = max(2.0, min(MAX_SPEED, self.recommended_speed))

        # Check grid traffic lights — IGNORE red lights most of the time
        inter, inter_dist = self._nearest_intersection()
        if inter and inter_dist < 100:
            from background_traffic import bg_traffic
            tl = bg_traffic.get_traffic_light_for(inter[0], inter[1])
            if tl is not None:
                my_axis = self._get_movement_axis()
                if not tl.is_green_for_axis(my_axis):
                    if random.random() < DRUNK_IGNORE_RED_CHANCE:
                        # IGNORE red light!
                        self.decision = "go"
                        self.reason = "drunk_ignores_red"
                        self.recommended_speed = max(self.recommended_speed, self.target_speed * 0.8)

    def _run_loop_waypoint(self):
        """Intelligent waypoint-following loop for background traffic vehicles.
        Persistent vehicles never despawn — they turn at edges and at random intersections.
        """
        from background_traffic import (
            generate_continuation_waypoints,
            generate_random_turn_at_intersection,
            _snap_to_lane,
            INTERSECTIONS, LANE_OFFSET as BG_LANE_OFFSET,
        )

        yield_counter = 0
        TURN_CHANCE = 0.30  # 30% chance to turn at each intersection

        while self._running:
            # If we ran out of waypoints, generate continuation
            if not self._waypoints:
                if self.persistent:
                    new_wps, new_dir = generate_continuation_waypoints(
                        self.x, self.y, self.direction
                    )
                    if new_wps:
                        self._waypoints = new_wps
                        continue
                    else:
                        # Fallback: shouldn't happen, but just reverse
                        self.direction = (self.direction + 180) % 360
                        time.sleep(UPDATE_INTERVAL)
                        continue
                else:
                    break  # non-persistent: finish

            tx, ty = self._waypoints[0]
            dx = tx - self.x
            dy = ty - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < 10.0:
                # ── Reached waypoint ──
                reached_wp = self._waypoints.pop(0)

                # Snap position to the waypoint to prevent lane drift on turns
                # Check if there's a significant direction change
                if self._waypoints:
                    next_tx, next_ty = self._waypoints[0]
                    ndx = next_tx - reached_wp[0]
                    ndy = next_ty - reached_wp[1]
                    if abs(ndx) > 0.1 or abs(ndy) > 0.1:
                        new_dir = math.degrees(math.atan2(ndx, ndy)) % 360
                        old_dir = self.direction % 360
                        angle_diff = abs(new_dir - old_dir)
                        if angle_diff > 180:
                            angle_diff = 360 - angle_diff
                        if angle_diff > 30:
                            # Significant turn — snap to the waypoint position
                            self.x, self.y = reached_wp
                else:
                    # Last waypoint reached — for persistent, will generate
                    # continuation on next iteration
                    pass

                # ── Random turn decision at intersections ──
                if self._waypoints and not self.is_drunk and not self.is_emergency:
                    # Check if we're near an intersection (the waypoint we just
                    # reached was at an intersection)
                    wp_x, wp_y = reached_wp
                    at_intersection = any(
                        abs(wp_x - ix) < 15 and abs(wp_y - iy) < 15
                        for ix, iy in INTERSECTIONS
                    )
                    if at_intersection and random.random() < TURN_CHANCE:
                        turn_wps, turn_dir = generate_random_turn_at_intersection(
                            self.x, self.y, self.direction
                        )
                        if turn_wps:
                            # Replace remaining waypoints with turn route
                            self._waypoints = turn_wps
                            # Snap position for the turn
                            self.x, self.y = _snap_to_lane(self.x, self.y, self.direction)

                if not self._waypoints:
                    continue  # will generate continuation at top of loop

                tx, ty = self._waypoints[0]
                dx = tx - self.x
                dy = ty - self.y
                dist = math.sqrt(dx * dx + dy * dy)

            # Update direction toward waypoint
            if dist > 0.1:
                base_dir = math.degrees(math.atan2(dx, dy)) % 360
                if self.is_drunk:
                    t = time.time()
                    swerve = DRUNK_SWERVE_MAX * math.sin(2 * math.pi * t / DRUNK_SWERVE_PERIOD)
                    swerve += random.uniform(-4, 4)
                    self.direction = (base_dir + swerve) % 360
                else:
                    self.direction = base_dir

            # ── Intelligent decision making ──
            if self.is_drunk:
                self._bg_drunk_erratic_decision()
            else:
                self._bg_compute_risk_and_decision()

            # ── Turn speed reduction: slow down when approaching a corner ──
            if len(self._waypoints) >= 2 and not self.is_drunk:
                next_tx, next_ty = self._waypoints[0]
                after_tx, after_ty = self._waypoints[1]
                seg1_dx = next_tx - self.x
                seg1_dy = next_ty - self.y
                seg2_dx = after_tx - next_tx
                seg2_dy = after_ty - next_ty
                len1 = math.sqrt(seg1_dx ** 2 + seg1_dy ** 2)
                len2 = math.sqrt(seg2_dx ** 2 + seg2_dy ** 2)
                if len1 > 0.1 and len2 > 0.1:
                    cos_angle = (seg1_dx * seg2_dx + seg1_dy * seg2_dy) / (len1 * len2)
                    cos_angle = max(-1.0, min(1.0, cos_angle))
                    turn_angle = math.degrees(math.acos(cos_angle))
                    if turn_angle > 30 and dist < 50:
                        turn_factor = max(0.35, 1.0 - turn_angle / 120.0)
                        self.recommended_speed = min(
                            self.recommended_speed,
                            self.target_speed * turn_factor
                        )

            # Anti-deadlock
            if self.decision in ("yield", "stop"):
                yield_counter += 1
                if yield_counter > 60:
                    self.decision = "go"
                    self.reason = "anti_deadlock"
                    self.recommended_speed = self.target_speed
                    yield_counter = 0
            else:
                yield_counter = 0

            # Adjust speed
            if self.speed < self.recommended_speed:
                self.speed = min(self.speed + ACCELERATION * UPDATE_INTERVAL, self.recommended_speed)
            elif self.speed > self.recommended_speed:
                self.speed = max(self.speed - DECELERATION * UPDATE_INTERVAL, self.recommended_speed)

            # Move
            if self.speed > 0.01:
                rad = math.radians(self.direction)
                self.x += self.speed * math.sin(rad) * UPDATE_INTERVAL
                self.y += self.speed * math.cos(rad) * UPDATE_INTERVAL

            channel.publish(self._build_message())
            time.sleep(UPDATE_INTERVAL)

        # Done — remove self (only for non-persistent)
        self._running = False
        channel.remove_agent(self.agent_id)

    def _run_loop(self):
        # Background vehicles use simple waypoint navigation
        if self._is_background:
            self._run_loop_waypoint()
            return

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
        self._passed_intersection = False
        self._fallback_consecutive = 0
        self._fallback_last_action = None
        self._llm_brain.reset()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_state(self):
        state = {
            "agent_id": self.agent_id, "agent_type": "vehicle",
            "x": round(self.x, 2), "y": round(self.y, 2),
            "speed": round(self.speed, 2), "direction": self.direction,
            "intention": self.intention, "risk_level": self.risk_level,
            "decision": self.decision, "reason": self.reason,
            "is_emergency": self.is_emergency,
            "is_drunk": self.is_drunk,
        }
        # Include LLM + memory stats
        llm_stats = self._llm_brain.get_stats()
        state["llm_calls"] = llm_stats["llm_calls"]
        state["llm_errors"] = llm_stats["llm_errors"]
        state["memory_decisions"] = llm_stats.get("memory_decisions", 0)
        state["near_misses"] = llm_stats.get("near_misses", 0)
        state["v2x_alerts_received"] = llm_stats.get("v2x_alerts_received", 0)
        state["lessons_learned"] = llm_stats.get("lessons_learned", 0)
        return state
