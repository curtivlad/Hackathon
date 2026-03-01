
import time
import threading
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("intersection_coordinator")

PHASE_DURATION = 12.0
GREEN_WAVE_SPEED = 13.0


class CoordinatedTrafficLight:

    def __init__(self, x: float, y: float, phase_offset: float = 0.0):
        self.x = x
        self.y = y
        self.phase_offset = phase_offset
        self.phase = "NS_GREEN"
        self._global_timer = 0.0

    def update_from_global(self, global_time: float):
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

    def __init__(self, intersections: List[Tuple[float, float]], grid_spacing: float):
        self._lock = threading.Lock()
        self._global_time = 0.0
        self._lights: Dict[Tuple[float, float], CoordinatedTrafficLight] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        x_coords = sorted(set(x for x, y in intersections))
        y_coords = sorted(set(y for x, y in intersections))

        for ix, iy in intersections:
            col_idx = x_coords.index(ix) if ix in x_coords else 0
            row_idx = y_coords.index(iy) if iy in y_coords else 0

            travel_time = grid_spacing / GREEN_WAVE_SPEED
            offset = (col_idx * travel_time + row_idx * travel_time * 0.5) % (PHASE_DURATION * 2)

            light = CoordinatedTrafficLight(ix, iy, phase_offset=offset)
            self._lights[(ix, iy)] = light

        logger.info(
            f"IntersectionCoordinator: {len(self._lights)} intersectii coordonate, "
            f"green-wave speed={GREEN_WAVE_SPEED} m/s, phase={PHASE_DURATION}s"
        )

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logger.info("IntersectionCoordinator started")

    def stop(self):
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
        with self._lock:
            light = self._lights.get((x, y))
            if light:
                return light.phase
        return None

    def get_light(self, x: float, y: float) -> Optional[CoordinatedTrafficLight]:
        with self._lock:
            for key, light in self._lights.items():
                if abs(key[0] - x) < 1.0 and abs(key[1] - y) < 1.0:
                    return light
        return None

    def get_all_states(self) -> List[dict]:
        with self._lock:
            return [light.to_dict() for light in self._lights.values()]

    def get_stats(self) -> dict:
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
