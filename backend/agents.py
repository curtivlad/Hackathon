"""
agents.py
Defineste agentii AI din simulare:
- VehicleAgent: un vehicul autonom care se misca, comunica V2X si ia decizii
- InfrastructureAgent: semaforul inteligent (V2I) care coordoneaza intersectia
"""

import math
import time
import threading
from v2x_channel import V2XChannel, V2XMessage, channel
from collision_detector import compute_risk_for_agent, distance, INTERSECTION_CENTER
from priority_negotiation import compute_decisions_for_all, compute_recommended_speed


# --- Configuratie vehicule ---
VEHICLE_LENGTH = 4.5      # metri
MAX_SPEED = 14.0          # ~50 km/h
MIN_SPEED = 0.0
ACCELERATION = 2.0        # m/s^2
DECELERATION = 4.0        # m/s^2
UPDATE_INTERVAL = 0.1     # secunde intre update-uri (10 fps simulare)


class VehicleAgent:
    """
    Agent vehicul autonom.
    Se misca pe o traiectorie, comunica prin V2X si evita coliziunile.
    """

    def _init_(
        self,
        agent_id: str,
        start_x: float,
        start_y: float,
        direction: float,
        initial_speed: float = 10.0,
        intention: str = "straight",
        is_emergency: bool = False,
        target_speed: float = 10.0,
    ):
        self.agent_id = agent_id
        self.x = start_x
        self.y = start_y
        self.direction = direction      # grade (0=Nord, 90=Est, etc.)
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
        """Actualizeaza pozitia pe baza vitezei si directiei."""
        rad = math.radians(self.direction)
        self.x += self.speed * math.sin(rad) * UPDATE_INTERVAL
        self.y += self.speed * math.cos(rad) * UPDATE_INTERVAL

    def _adjust_speed(self):
        """Ajusteaza viteza catre viteza tinta (accelerare/franare)."""
        if self.speed < self.recommended_speed:
            self.speed = min(self.speed + ACCELERATION * UPDATE_INTERVAL, self.recommended_speed)
        elif self.speed > self.recommended_speed:
            self.speed = max(self.speed - DECELERATION * UPDATE_INTERVAL, self.recommended_speed)

    def _make_decision(self):
        """Citeste canalul V2X si ia o decizie de viteza."""
        others = channel.get_other_agents(self.agent_id)
        all_agents = channel.get_all_states()

        # Calculeaza riscul propriu
        self.risk_level = compute_risk_for_agent(
            channel.get_agent_state(self.agent_id) or self._build_message(),
            others
        )

        # Obtine decizia din negocierea de prioritate
        if all_agents:
            decisions = compute_decisions_for_all(all_agents)
            my_decision = decisions.get(self.agent_id, {"decision": "go", "reason": "clear"})
            self.decision = my_decision["decision"]
            self.reason = my_decision["reason"]
        else:
            self.decision = "go"
            self.reason = "no_traffic"

        # Calculeaza viteza recomandata
        msg = self._build_message()
        self.recommended_speed = compute_recommended_speed(msg, self.decision)

        # Urgenta: ignora restrictiile daca e vehicul de urgenta
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
        """Verifica daca vehiculul a trecut de intersectie."""
        dist = distance(self.x, self.y, *INTERSECTION_CENTER)
        if dist < 15.0:
            self._passed_intersection = True
        # Dupa ce a trecut, continua pana la distanta mare
        if self._passed_intersection and dist > 120.0:
            return True
        return False

    def _run_loop(self):
        """Bucla principala a agentului (ruleaza intr-un thread separat)."""
        while self._running:
            self._make_decision()
            self._adjust_speed()
            self._update_position()

            # Publica starea pe canalul V2X
            channel.publish(self._build_message())

            # Verifica daca a iesit din scena
            if self._check_passed_intersection():
                self.stop()
                channel.remove_agent(self.agent_id)
                break

            time.sleep(UPDATE_INTERVAL)

    def start(self):
        """Porneste agentul intr-un thread separat."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Opreste agentul."""
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


class InfrastructureAgent:
    """
    Agent infrastructura — semafor inteligent V2I.
    Monitorizeaza traficul si trimite recomandari de viteza vehiculelor.
    """

    PHASE_DURATION = 10.0   # secunde per faza semafor

    def _init_(self):
        self.agent_id = "infrastructure_traffic_light"
        self.phase = "NS_GREEN"   # NS_GREEN sau EW_GREEN
        self.phase_timer = 0.0
        self.recommendations: dict = {}
        self._running = False
        self._thread = None
        self.active_vehicles = 0
        self.collisions_prevented = 0

    def _update_phase(self):
        """Schimba faza semaforului."""
        self.phase_timer += UPDATE_INTERVAL
        if self.phase_timer >= self.PHASE_DURATION:
            self.phase_timer = 0.0
            self.phase = "EW_GREEN" if self.phase == "NS_GREEN" else "NS_GREEN"

    def _is_green_for(self, agent: V2XMessage) -> bool:
        """Verifica daca semaforul este verde pentru directia agentului."""
        from collision_detector import get_velocity_components
        vx, vy = get_velocity_components(agent.speed, agent.direction)

        # Nord-Sud: miscare predominant pe Y
        if abs(vy) > abs(vx):
            return self.phase == "NS_GREEN"
        else:
            return self.phase == "EW_GREEN"

    def _send_recommendations(self):
        """Calculeaza si trimite recomandari de viteza tuturor vehiculelor."""
        all_states = channel.get_all_states()
        self.active_vehicles = len([v for v in all_states.values() if v.agent_type == "vehicle"])

        recommendations = {}
        for agent_id, agent in all_states.items():
            if agent.agent_type != "vehicle":
                continue

            dist = distance(agent.x, agent.y, *INTERSECTION_CENTER)

            if dist > 80.0:
                # Departe de intersectie: viteza normala
                rec_speed = min(agent.speed, MAX_SPEED)
                rec_action = "maintain_speed"
            elif self._is_green_for(agent):
                # Verde: poate trece, dar reduce viteza in intersectie
                if dist < 20.0:
                    rec_speed = min(agent.speed, 8.0)
                    rec_action = "slow_in_intersection"
                else:
                    rec_speed = min(agent.speed, 12.0)
                    rec_action = "proceed"
            else:
                # Rosu: opreste inainte de intersectie
                stopping_distance = (agent.speed ** 2) / (2 * DECELERATION)
                if dist <= stopping_distance + 5.0:
                    rec_speed = 0.0
                    rec_action = "stop_red_light"
                else:
                    # Inca are timp sa incetineasca lin
                    rec_speed = agent.speed * 0.7
                    rec_action = "decelerate_red"

            recommendations[agent_id] = {
                "recommended_speed": round(rec_speed, 1),
                "action": rec_action,
                "phase": self.phase,
            }

        self.recommendations = recommendations

        # Publica starea infrastructurii pe canal
        channel.publish(V2XMessage(
            agent_id=self.agent_id,
            agent_type="infrastructure",
            x=0.0,
            y=0.0,
            speed=0.0,
            direction=0.0,
            intention=self.phase,
            risk_level="low",
            decision=self.phase,
        ))

    def _run_loop(self):
        while self._running:
            self._update_phase()
            self._send_recommendations()
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
            "phase": self.phase,
            "phase_timer": round(self.phase_timer, 1),
            "phase_remaining": round(self.PHASE_DURATION - self.phase_timer, 1),
            "active_vehicles": self.active_vehicles,
            "collisions_prevented": self.collisions_prevented,
            "recommendations": self.recommendations,
        }