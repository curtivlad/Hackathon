"""
background_traffic.py — Manager pentru trafic ambient pe grila de intersectii.
Genereaza masini random cu trasee predefinite (waypoints) prin oras.
Include semafoare pe unele intersectii si masini de urgenta ocazionale.
"""

import math
import time
import random
import threading
import logging
from typing import List, Tuple, Optional, Dict
from agents import VehicleAgent
from v2x_channel import channel

logger = logging.getLogger("background_traffic")

# ──────────────────────── Grid Configuration ────────────────────────
GRID_COLS = 3
GRID_ROWS = 3
GRID_SPACING = 300.0

_half_w = (GRID_COLS - 1) * GRID_SPACING / 2
_half_h = (GRID_ROWS - 1) * GRID_SPACING / 2

INTERSECTIONS: List[Tuple[float, float]] = []
for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        ix = -_half_w + col * GRID_SPACING
        iy = _half_h - row * GRID_SPACING
        INTERSECTIONS.append((ix, iy))

DEMO_INTERSECTION = min(INTERSECTIONS, key=lambda p: p[0]**2 + p[1]**2)

LANE_OFFSET = 10.0
SPAWN_MARGIN = 140.0

# Background traffic settings
MAX_BG_VEHICLES = 10
SPAWN_INTERVAL = 2.5
BG_SPEED_MIN = 7.0
BG_SPEED_MAX = 12.0
EMERGENCY_CHANCE = 0.08  # 8% chance a BG vehicle is an ambulance
MIN_SPAWN_DISTANCE = 60.0  # minimum distance between vehicles on same lane

# ──────────────────────── Traffic Lights on Grid ────────────────────────
# Layout:
#   Row top    (y=300):  traffic light on LEFT   column (-300, 300)
#   Row middle (y=0):    traffic light on RIGHT  column ( 300,   0)
#   Row bottom (y=-300): traffic light on MIDDLE column (   0,-300)
TRAFFIC_LIGHT_PHASE_DURATION = 12.0  # seconds per phase

TRAFFIC_LIGHT_INTERSECTIONS = [
    (-300.0,  300.0),   # top-left
    ( 300.0,    0.0),   # middle-right
    (   0.0, -300.0),   # bottom-middle
]


class GridTrafficLight:
    """Simple traffic light for a grid intersection (not the demo one)."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.phase = "NS_GREEN"
        self.phase_timer = random.uniform(0, TRAFFIC_LIGHT_PHASE_DURATION)  # random offset

    def update(self, dt: float):
        self.phase_timer += dt
        if self.phase_timer >= TRAFFIC_LIGHT_PHASE_DURATION:
            self.phase_timer = 0.0
            self.phase = "EW_GREEN" if self.phase == "NS_GREEN" else "NS_GREEN"

    def is_green_for_axis(self, axis: str) -> bool:
        if self.phase == "NS_GREEN":
            return axis == "NS"
        return axis == "EW"

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "phase": self.phase}


def get_grid_info() -> dict:
    return {
        "intersections": [{"x": ix, "y": iy} for ix, iy in INTERSECTIONS],
        "grid_cols": GRID_COLS,
        "grid_rows": GRID_ROWS,
        "grid_spacing": GRID_SPACING,
        "demo_intersection": {"x": DEMO_INTERSECTION[0], "y": DEMO_INTERSECTION[1]},
        "traffic_light_positions": [{"x": x, "y": y} for x, y in TRAFFIC_LIGHT_INTERSECTIONS],
    }


# ──────────────────────── Route Cooldown ────────────────────────
ROUTE_COOLDOWN = 10.0  # seconds before same route can be reused

# All possible routes as (axis, coord, direction) keys:
#   ("col", col_x, 180) = heading south on column col_x
#   ("col", col_x, 0)   = heading north on column col_x
#   ("row", row_y, 90)  = heading east  on row row_y
#   ("row", row_y, 270) = heading west  on row row_y
_ALL_COL_X = sorted(set(x for x, y in INTERSECTIONS))
_ALL_ROW_Y = sorted(set(y for x, y in INTERSECTIONS))

_ALL_ROUTE_KEYS = []
for cx in _ALL_COL_X:
    _ALL_ROUTE_KEYS.append(("col", cx, 180.0))
    _ALL_ROUTE_KEYS.append(("col", cx, 0.0))
for ry in _ALL_ROW_Y:
    _ALL_ROUTE_KEYS.append(("row", ry, 90.0))
    _ALL_ROUTE_KEYS.append(("row", ry, 270.0))


def _build_route(route_key) -> Tuple[List[Tuple[float, float]], float]:
    """Build waypoints for a given route key."""
    axis, coord, direction = route_key

    if axis == "col":
        col_x = coord
        if direction == 180.0:  # heading south
            lane_x = col_x - LANE_OFFSET
            row_y_values = sorted(set(y for x, y in INTERSECTIONS if x == col_x), reverse=True)
            start_y = row_y_values[0] + SPAWN_MARGIN
            end_y = row_y_values[-1] - SPAWN_MARGIN
            waypoints = [(lane_x, start_y)]
            for ry in row_y_values:
                waypoints.append((lane_x, ry))
            waypoints.append((lane_x, end_y))
        else:  # direction == 0.0, heading north
            lane_x = col_x + LANE_OFFSET
            row_y_values = sorted(set(y for x, y in INTERSECTIONS if x == col_x))
            start_y = row_y_values[0] - SPAWN_MARGIN
            end_y = row_y_values[-1] + SPAWN_MARGIN
            waypoints = [(lane_x, start_y)]
            for ry in row_y_values:
                waypoints.append((lane_x, ry))
            waypoints.append((lane_x, end_y))
    else:  # axis == "row"
        row_y = coord
        if direction == 90.0:  # heading east
            lane_y = row_y - LANE_OFFSET
            col_x_values = sorted(set(x for x, y in INTERSECTIONS if y == row_y))
            start_x = col_x_values[0] - SPAWN_MARGIN
            end_x = col_x_values[-1] + SPAWN_MARGIN
            waypoints = [(start_x, lane_y)]
            for cx in col_x_values:
                waypoints.append((cx, lane_y))
            waypoints.append((end_x, lane_y))
        else:  # direction == 270.0, heading west
            lane_y = row_y + LANE_OFFSET
            col_x_values = sorted(set(x for x, y in INTERSECTIONS if y == row_y), reverse=True)
            start_x = col_x_values[0] + SPAWN_MARGIN
            end_x = col_x_values[-1] - SPAWN_MARGIN
            waypoints = [(start_x, lane_y)]
            for cx in col_x_values:
                waypoints.append((cx, lane_y))
            waypoints.append((end_x, lane_y))

    return waypoints, direction


class BackgroundTrafficManager:
    """Manages ambient background traffic on the city grid."""

    def __init__(self):
        self._vehicles: Dict[str, VehicleAgent] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._counter = 0
        self._lock = threading.Lock()
        # Grid traffic lights
        self._traffic_lights: List[GridTrafficLight] = [
            GridTrafficLight(x, y) for x, y in TRAFFIC_LIGHT_INTERSECTIONS
        ]
        self._tl_thread: Optional[threading.Thread] = None
        # Route cooldown: route_key -> last_used_timestamp
        self._route_cooldowns: Dict[tuple, float] = {}

    @property
    def active(self) -> bool:
        return self._running

    def get_traffic_light_states(self) -> List[dict]:
        """Return current state of all grid traffic lights."""
        return [tl.to_dict() for tl in self._traffic_lights]

    def get_traffic_light_for(self, x: float, y: float) -> Optional[GridTrafficLight]:
        """Return traffic light at a given intersection, or None."""
        for tl in self._traffic_lights:
            if abs(tl.x - x) < 1.0 and abs(tl.y - y) < 1.0:
                return tl
        return None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spawn_loop, daemon=True)
        self._thread.start()
        self._tl_thread = threading.Thread(target=self._tl_loop, daemon=True)
        self._tl_thread.start()
        logger.info("Background traffic started")

    def stop(self):
        self._running = False
        with self._lock:
            for v in self._vehicles.values():
                v.stop()
                channel.remove_agent(v.agent_id)
            self._vehicles.clear()
        logger.info("Background traffic stopped")

    def _tl_loop(self):
        """Update grid traffic lights."""
        dt = 0.2
        while self._running:
            for tl in self._traffic_lights:
                tl.update(dt)
            time.sleep(dt)

    def _spawn_loop(self):
        while self._running:
            self._cleanup()
            with self._lock:
                active_count = len(self._vehicles)
            if active_count < MAX_BG_VEHICLES:
                self._spawn_vehicle()
            time.sleep(SPAWN_INTERVAL)

    def _cleanup(self):
        with self._lock:
            finished = [vid for vid, v in self._vehicles.items() if not v._running]
            for vid in finished:
                channel.remove_agent(vid)
                del self._vehicles[vid]

    def _is_spawn_blocked(self, start_x: float, start_y: float, direction: float) -> bool:
        """Check if another vehicle is too close to the spawn point on the same lane."""
        all_states = channel.get_all_states()
        for msg in all_states.values():
            if msg.agent_type != "vehicle":
                continue
            d = math.sqrt((msg.x - start_x)**2 + (msg.y - start_y)**2)
            if d < MIN_SPAWN_DISTANCE:
                # Same general direction? (within 30 degrees)
                angle_diff = abs(msg.direction - direction) % 360
                if angle_diff < 30 or angle_diff > 330:
                    return True
        return False

    def _spawn_vehicle(self):
        """Spawn a new background vehicle with a random route, avoiding recently used routes."""
        now = time.time()

        # Filter out routes that are on cooldown
        available_keys = [
            rk for rk in _ALL_ROUTE_KEYS
            if now - self._route_cooldowns.get(rk, 0) >= ROUTE_COOLDOWN
        ]

        if not available_keys:
            return  # all routes on cooldown, wait

        # Shuffle and try routes until we find one not spawn-blocked
        random.shuffle(available_keys)
        for route_key in available_keys:
            waypoints, direction = _build_route(route_key)
            if len(waypoints) < 2:
                continue
            start_x, start_y = waypoints[0]
            if not self._is_spawn_blocked(start_x, start_y, direction):
                # Found a good route
                speed = random.uniform(BG_SPEED_MIN, BG_SPEED_MAX)
                is_emergency = random.random() < EMERGENCY_CHANCE

                self._counter += 1
                agent_id = f"BG_{self._counter:03d}"

                vehicle = VehicleAgent(
                    agent_id=agent_id,
                    start_x=start_x,
                    start_y=start_y,
                    direction=direction,
                    initial_speed=speed,
                    target_speed=speed if not is_emergency else min(speed * 1.4, 14.0),
                    intention="straight",
                    is_emergency=is_emergency,
                    waypoints=waypoints[1:],
                )

                with self._lock:
                    self._vehicles[agent_id] = vehicle

                # Record cooldown for this route
                self._route_cooldowns[route_key] = now

                vehicle.start()
                etype = " [EMERGENCY]" if is_emergency else ""
                logger.debug(f"Spawned {agent_id}{etype} at ({start_x:.0f}, {start_y:.0f}) dir={direction}")
                return

        # All routes blocked, skip this cycle

    def get_vehicle_count(self) -> int:
        with self._lock:
            return len(self._vehicles)


bg_traffic = BackgroundTrafficManager()




