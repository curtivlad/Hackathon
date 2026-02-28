"""
infrastructure_agent.py
Agentul de infrastructura — semafor inteligent cu logica V2I avansata.

Functionalitati:
  - Faze semafor adaptive (NS_GREEN / EW_GREEN)
  - Detectie vehicul de urgenta -> preemptare semafor
  - Recomandari de viteza personalizate per vehicul (Green Wave)
  - Monitorizare trafic: numar vehicule, coliziuni prevenite, timp mediu de tranzit
  - Publicare stare pe canalul V2X
"""

import time
import threading
import math
from typing import Dict, Optional
from v2x_channel import V2XChannel, V2XMessage, channel
from collision_detector import distance, INTERSECTION_CENTER, get_collision_pairs

# ------------------------------------------------------------------ #
#  Constante                                                          #
# ------------------------------------------------------------------ #

UPDATE_INTERVAL   = 0.1     # secunde intre update-uri
DECELERATION      = 4.0     # m/s^2 — franare normala vehicul
MAX_SPEED         = 14.0    # m/s  — ~50 km/h
PHASE_DURATION    = 10.0    # secunde per faza normala
EMERGENCY_PHASE   = 15.0    # faza extinsa pentru vehicul urgenta

# Distante (metri)
STOP_LINE_DIST    = 25.0    # distanta de la centru la linia de stop
SLOW_ZONE_DIST    = 50.0    # zona de incetinire in intersectie
APPROACH_DIST     = 100.0   # distanta de la care incepe monitorizarea


# ------------------------------------------------------------------ #
#  Helper geometry                                                    #
# ------------------------------------------------------------------ #

def get_movement_axis(agent: V2XMessage) -> str:
    """
    Determina daca vehiculul se misca predominant pe axa N-S sau E-W.
    Returneaza: 'NS' sau 'EW'
    """
    rad = math.radians(agent.direction)
    vx = abs(math.sin(rad))
    vy = abs(math.cos(rad))
    return "NS" if vy >= vx else "EW"


def stopping_distance(speed: float) -> float:
    """Distanta minima de oprire la viteza curenta."""
    return (speed ** 2) / (2 * DECELERATION) if speed > 0 else 0.0


# ------------------------------------------------------------------ #
#  InfrastructureAgent                                                #
# ------------------------------------------------------------------ #

class InfrastructureAgent:
    """
    Semafor inteligent cu comunicare V2I bidirectionala.

    Faze:
      NS_GREEN  — Nord-Sud au verde, Est-Vest au rosu
      EW_GREEN  — Est-Vest au verde, Nord-Sud au rosu
      EMERGENCY — Toate rosii, exceptand directia vehiculului de urgenta
    """

    def __init__(self):
        self.agent_id        = "INFRA_TL_01"
        self.phase           = "NS_GREEN"
        self.phase_timer     = 0.0
        self.phase_duration  = PHASE_DURATION
        self.emergency_mode  = False
        self.emergency_axis  = None           # 'NS' sau 'EW'

        # Recomandari trimise vehiculelor
        self.recommendations: Dict[str, dict] = {}

        # Statistici
        self.stats = {
            "collisions_prevented": 0,
            "vehicles_processed":   0,
            "emergency_preemptions": 0,
            "phase_changes":        0,
            "uptime":               0.0,
        }

        # Vehicule urmarite (pentru tranzit time)
        self._tracked_vehicles: Dict[str, float] = {}   # id -> timestamp intrare
        self._prev_collision_pairs = set()

        self._running = False
        self._thread  = None
        self._start_time = None

    # ---------------------------------------------------------------- #
    #  Faze semafor                                                     #
    # ---------------------------------------------------------------- #

    def _get_green_axis(self) -> str:
        """Returneaza axa care are verde acum."""
        if self.emergency_mode and self.emergency_axis:
            return self.emergency_axis
        return "NS" if self.phase == "NS_GREEN" else "EW"

    def _is_green_for(self, agent: V2XMessage) -> bool:
        """Verifica daca semaforul este verde pentru un vehicul."""
        return get_movement_axis(agent) == self._get_green_axis()

    def _detect_emergency(self, all_states: Dict[str, V2XMessage]) -> Optional[str]:
        """
        Detecteaza un vehicul de urgenta in apropiere.
        Returneaza axa de deplasare a vehiculului de urgenta, sau None.
        """
        for agent in all_states.values():
            if agent.agent_type != "vehicle":
                continue
            if not agent.is_emergency:
                continue
            dist = distance(agent.x, agent.y, *INTERSECTION_CENTER)
            if dist < APPROACH_DIST:
                return get_movement_axis(agent)
        return None

    def _update_phase(self, all_states: Dict[str, V2XMessage]):
        """Actualizeaza faza semaforului, cu logica de preemptare urgenta."""

        # Detectie urgenta
        emergency_axis = self._detect_emergency(all_states)

        if emergency_axis:
            if not self.emergency_mode:
                # Intra in modul urgenta
                self.emergency_mode  = True
                self.emergency_axis  = emergency_axis
                self.phase_timer     = 0.0
                self.phase_duration  = EMERGENCY_PHASE
                self.stats["emergency_preemptions"] += 1

                # Schimba faza daca e necesar
                if emergency_axis == "NS" and self.phase != "NS_GREEN":
                    self.phase = "NS_GREEN"
                    self.stats["phase_changes"] += 1
                elif emergency_axis == "EW" and self.phase != "EW_GREEN":
                    self.phase = "EW_GREEN"
                    self.stats["phase_changes"] += 1
        else:
            # Iese din modul urgenta
            if self.emergency_mode:
                self.emergency_mode = False
                self.emergency_axis = None
                self.phase_duration = PHASE_DURATION
                self.phase_timer    = 0.0

            # Rotatie normala de faze
            self.phase_timer += UPDATE_INTERVAL
            if self.phase_timer >= self.phase_duration:
                self.phase_timer = 0.0
                self.phase = "EW_GREEN" if self.phase == "NS_GREEN" else "NS_GREEN"
                self.stats["phase_changes"] += 1

    # ---------------------------------------------------------------- #
    #  Recomandari V2I                                                  #
    # ---------------------------------------------------------------- #

    def _compute_recommendations(self, all_states: Dict[str, V2XMessage]):
        """
        Calculeaza recomandari de viteza pentru fiecare vehicul.
        Logica Green Wave: daca ai verde, recomanda viteza optima sa ajungi fara sa frenezi.
        """
        recommendations = {}

        for agent_id, agent in all_states.items():
            if agent.agent_type != "vehicle":
                continue

            dist = distance(agent.x, agent.y, *INTERSECTION_CENTER)

            # Vehiculul a trecut deja intersectia
            if dist < 5.0:
                rec = {
                    "recommended_speed": min(agent.speed, MAX_SPEED),
                    "action":            "clear_intersection",
                    "signal":            "GREEN",
                    "time_to_green":     0.0,
                }
                recommendations[agent_id] = rec
                continue

            green_for_agent = self._is_green_for(agent)
            time_remaining  = self.phase_duration - self.phase_timer

            # --- Verde ---
            if green_for_agent:
                if dist > SLOW_ZONE_DIST:
                    # Green Wave: calculeaza viteza optima sa ajunga cand e inca verde
                    time_to_arrive = dist / agent.speed if agent.speed > 0.1 else float('inf')

                    if time_to_arrive <= time_remaining:
                        # Ajunge cu verde — mentine viteza
                        rec_speed = min(agent.speed, MAX_SPEED)
                        action    = "maintain_speed_green"
                    else:
                        # Ajunge dupa ce se schimba — incetineste sa prinda urmatorul verde
                        next_green_in = time_remaining + PHASE_DURATION
                        if next_green_in > 0:
                            rec_speed = dist / next_green_in
                            rec_speed = max(2.0, min(rec_speed, MAX_SPEED))
                        else:
                            rec_speed = agent.speed
                        action = "adjust_for_next_green"
                else:
                    # In zona de incetinire
                    rec_speed = min(agent.speed, 8.0)
                    action    = "slow_in_intersection"

                recommendations[agent_id] = {
                    "recommended_speed": round(rec_speed, 1),
                    "action":            action,
                    "signal":            "GREEN",
                    "time_to_green":     0.0,
                }

            # --- Rosu ---
            else:
                stop_dist = stopping_distance(agent.speed)
                time_to_arrive = dist / agent.speed if agent.speed > 0.1 else float('inf')
                # Urmatorul verde pentru acest agent
                time_to_next_green = time_remaining + PHASE_DURATION

                if dist <= stop_dist + STOP_LINE_DIST:
                    # Trebuie sa frâneze acum
                    rec_speed = 0.0
                    action    = "stop_red_light"
                elif dist <= APPROACH_DIST:
                    # Incetineste gradual
                    target_speed = dist / time_to_next_green if time_to_next_green > 0 else 0.0
                    rec_speed    = max(0.0, min(target_speed, agent.speed * 0.75))
                    action       = "decelerate_for_red"
                else:
                    rec_speed = agent.speed
                    action    = "prepare_to_stop"

                recommendations[agent_id] = {
                    "recommended_speed": round(rec_speed, 1),
                    "action":            action,
                    "signal":            "RED",
                    "time_to_green":     round(time_to_next_green, 1),
                }

            # Override: vehicul de urgenta ignora semaforul
            if agent.is_emergency:
                recommendations[agent_id] = {
                    "recommended_speed": MAX_SPEED,
                    "action":            "emergency_override",
                    "signal":            "GREEN",
                    "time_to_green":     0.0,
                }

        self.recommendations = recommendations

    # ---------------------------------------------------------------- #
    #  Statistici                                                       #
    # ---------------------------------------------------------------- #

    def _update_stats(self, all_states: Dict[str, V2XMessage]):
        """Actualizeaza statisticile de trafic."""

        vehicle_ids = {k for k, v in all_states.items() if v.agent_type == "vehicle"}

        # Vehicule noi intrate in monitorizare
        for vid in vehicle_ids:
            if vid not in self._tracked_vehicles:
                self._tracked_vehicles[vid] = time.time()
                self.stats["vehicles_processed"] += 1

        # Vehicule care au iesit
        exited = set(self._tracked_vehicles) - vehicle_ids
        for vid in exited:
            del self._tracked_vehicles[vid]

        # Coliziuni prevenite
        pairs         = get_collision_pairs(all_states)
        current_risks = {(p["agent1"], p["agent2"]) for p in pairs if p["risk"] == "collision"}

        for pair in self._prev_collision_pairs:
            if pair not in current_risks:
                self.stats["collisions_prevented"] += 1

        self._prev_collision_pairs = current_risks

        # Uptime
        if self._start_time:
            self.stats["uptime"] = round(time.time() - self._start_time, 1)

    # ---------------------------------------------------------------- #
    #  Publicare V2X                                                    #
    # ---------------------------------------------------------------- #

    def _publish(self):
        """Publica starea infrastructurii pe canalul V2X."""
        channel.publish(V2XMessage(
            agent_id    = self.agent_id,
            agent_type  = "infrastructure",
            x           = 0.0,
            y           = 0.0,
            speed       = 0.0,
            direction   = 0.0,
            intention   = self.phase,
            risk_level  = "low",
            decision    = "EMERGENCY" if self.emergency_mode else self.phase,
        ))

    # ---------------------------------------------------------------- #
    #  Bucla principala                                                 #
    # ---------------------------------------------------------------- #

    def _run_loop(self):
        while self._running:
            all_states = channel.get_all_states()

            self._update_phase(all_states)
            self._compute_recommendations(all_states)
            self._update_stats(all_states)
            self._publish()

            time.sleep(UPDATE_INTERVAL)

    def start(self):
        self._running    = True
        self._start_time = time.time()
        self._thread     = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        channel.remove_agent(self.agent_id)

    # ---------------------------------------------------------------- #
    #  Stare pentru frontend / API                                     #
    # ---------------------------------------------------------------- #

    def get_state(self) -> dict:
        return {
            "agent_id":        self.agent_id,
            "phase":           self.phase,
            "phase_timer":     round(self.phase_timer, 1),
            "phase_remaining": round(self.phase_duration - self.phase_timer, 1),
            "phase_duration":  self.phase_duration,
            "emergency_mode":  self.emergency_mode,
            "emergency_axis":  self.emergency_axis,
            "recommendations": self.recommendations,
            "stats":           self.stats,
        }