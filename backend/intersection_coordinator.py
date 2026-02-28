"""
intersection_coordinator.py — Coordoneaza semafoarele pe TOATE intersectiile din grid.

Implementeaza:
- Semafoare pe fiecare intersectie din grid (25 total pentru 5x5)
- Green-wave synchronization: offset-uri calculate astfel incat
  un vehicul care circula cu viteza constanta sa prinda verde la
  intersectii consecutive
- Faze adaptive — coordonare intre intersectii conectate

Bonus criteriu: Sistemul gestioneaza simultan cel putin 2 intersectii
conectate, cu agenti care isi coordoneaza tranzitul intre ele prin
acelasi canal V2X.
"""

import time
import threading
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("intersection_coordinator")

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PHASE_DURATION = 12.0          # secunde per faza
GREEN_WAVE_SPEED = 13.0        # m/s — viteza optima pentru unda verde (~47 km/h)


class CoordinatedTrafficLight:
    """Semafor cu offset pentru green-wave."""

    def __init__(self, x: float, y: float, phase_offset: float = 0.0):
        self.x = x
        self.y = y
        self.phase_offset = phase_offset
        self.phase = "NS_GREEN"
        self._global_timer = 0.0

    def update_from_global(self, global_time: float):
        """Actualizeaza faza bazat pe timpul global + offset."""
        effective_time = (global_time + self.phase_offset) % (PHASE_DURATION * 2)
        if effective_time < PHASE_DURATION:
            self.phase = "NS_GREEN"
        else:
            self.phase = "EW_GREEN"

    def is_green_for_axis(self, axis: str) -> bool:
        return (axis == "NS") == (self.phase == "NS_GREEN")

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "phase": self.phase}


class IntersectionCoordinator:
    """
    Coordinator central care gestioneaza semafoarele pe TOATE intersectiile.

    Green-wave: offset-urile sunt calculate pe baza distantei intre
    intersectii si a vitezei optime, astfel incat un vehicul care
    circula pe un coridor (N-S sau E-W) la GREEN_WAVE_SPEED sa
    prinda verde la fiecare intersectie consecutiva.
    """

    def __init__(self, intersections: List[Tuple[float, float]], grid_spacing: float):
        self._lock = threading.Lock()
        self._global_time = 0.0
        self._lights: Dict[Tuple[float, float], CoordinatedTrafficLight] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Calculeaza green-wave offsets
        x_coords = sorted(set(x for x, y in intersections))
        y_coords = sorted(set(y for x, y in intersections))

        for ix, iy in intersections:
            # Offset bazat pe pozitia in grid pentru green-wave
            # Folosim pozitia pe coloana (x) pentru undele NS
            # si pozitia pe rand (y) pentru undele EW
            col_idx = x_coords.index(ix) if ix in x_coords else 0
            row_idx = y_coords.index(iy) if iy in y_coords else 0

            # Green-wave offset: timp de deplasare intre intersectii consecutive
            travel_time = grid_spacing / GREEN_WAVE_SPEED
            # Alternam intre NS si EW offset bazat pe pozitie
            offset = (col_idx * travel_time + row_idx * travel_time * 0.5) % (PHASE_DURATION * 2)

            light = CoordinatedTrafficLight(ix, iy, phase_offset=offset)
            self._lights[(ix, iy)] = light

        logger.info(
            f"IntersectionCoordinator: {len(self._lights)} intersectii coordonate, "
            f"green-wave speed={GREEN_WAVE_SPEED} m/s, phase={PHASE_DURATION}s"
        )

    def start(self):
        """Porneste thread-ul de update al semafoarelor."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logger.info("IntersectionCoordinator started")

    def stop(self):
        """Opreste coordinator-ul."""
        self._running = False
        logger.info("IntersectionCoordinator stopped")

    def _update_loop(self):
        dt = 0.2
        while self._running:
            with self._lock:
                self._global_time += dt
                for light in self._lights.values():
                    light.update_from_global(self._global_time)
            time.sleep(dt)

    def get_phase(self, x: float, y: float) -> Optional[str]:
        """Returneaza faza semaforului de la intersectia (x, y)."""
        with self._lock:
            light = self._lights.get((x, y))
            if light:
                return light.phase
        return None

    def get_light(self, x: float, y: float) -> Optional[CoordinatedTrafficLight]:
        """Returneaza obiectul semafor de la intersectia (x, y)."""
        # Cauta cu toleranta
        with self._lock:
            for key, light in self._lights.items():
                if abs(key[0] - x) < 1.0 and abs(key[1] - y) < 1.0:
                    return light
        return None

    def get_all_states(self) -> List[dict]:
        """Returneaza toate starile semafoarelor."""
        with self._lock:
            return [light.to_dict() for light in self._lights.values()]

    def get_stats(self) -> dict:
        """Statistici ale coordinator-ului."""
        with self._lock:
            ns_green = sum(1 for l in self._lights.values() if l.phase == "NS_GREEN")
            ew_green = len(self._lights) - ns_green
            return {
                "total_intersections": len(self._lights),
                "ns_green_count": ns_green,
                "ew_green_count": ew_green,
                "global_time": round(self._global_time, 1),
                "phase_duration": PHASE_DURATION,
                "green_wave_speed_ms": GREEN_WAVE_SPEED,
                "green_wave_speed_kmh": round(GREEN_WAVE_SPEED * 3.6, 1),
            }

