"""
background_traffic.py — Manager pentru trafic ambient pe grila de intersectii.
Genereaza masini cu trasee variate (drept, viraj stanga/dreapta) prin oras.
Drumurile formeaza un patrat inchis — toate capetele sunt unite, nimic nu duce in gol.
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
GRID_COLS = 5
GRID_ROWS = 5
GRID_SPACING = 200.0

_half_w = (GRID_COLS - 1) * GRID_SPACING / 2
_half_h = (GRID_ROWS - 1) * GRID_SPACING / 2

INTERSECTIONS: List[Tuple[float, float]] = []
for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        ix = -_half_w + col * GRID_SPACING
        iy = _half_h - row * GRID_SPACING
        INTERSECTIONS.append((ix, iy))

DEMO_INTERSECTION = min(INTERSECTIONS, key=lambda p: p[0] ** 2 + p[1] ** 2)

LANE_OFFSET = 10.0

# Background traffic settings — dense traffic ecosystem
MAX_BG_VEHICLES = 30
SPAWN_INTERVAL = 1.2
BG_SPEED_MIN = 12.0
BG_SPEED_MAX = 20.0
EMERGENCY_CHANCE = 0.08
MIN_SPAWN_DISTANCE = 45.0

# ──────────────────────── Traffic Lights on Grid ────────────────────────
TRAFFIC_LIGHT_PHASE_DURATION = 12.0

TRAFFIC_LIGHT_INTERSECTIONS = [
    (-200.0, 200.0),
    (200.0, 200.0),
    (-200.0, -200.0),
    (200.0, -200.0),
]

_ALL_COL_X = sorted(set(x for x, y in INTERSECTIONS))
_ALL_ROW_Y = sorted(set(y for x, y in INTERSECTIONS))

_MIN_X, _MAX_X = min(_ALL_COL_X), max(_ALL_COL_X)
_MIN_Y, _MAX_Y = min(_ALL_ROW_Y), max(_ALL_ROW_Y)


class GridTrafficLight:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.phase = "NS_GREEN"
        self.phase_timer = random.uniform(0, TRAFFIC_LIGHT_PHASE_DURATION)

    def update(self, dt: float):
        self.phase_timer += dt
        if self.phase_timer >= TRAFFIC_LIGHT_PHASE_DURATION:
            self.phase_timer = 0.0
            self.phase = "EW_GREEN" if self.phase == "NS_GREEN" else "NS_GREEN"

    def is_green_for_axis(self, axis: str) -> bool:
        return (axis == "NS") == (self.phase == "NS_GREEN")

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
        "closed_loop": True,
    }


# ──────────────────────── Lane helpers ────────────────────────

def _lane_xy(ix, iy, direction):
    """Lane-offset position for European right-hand traffic."""
    d = direction % 360
    if d == 0:
        return (ix + LANE_OFFSET, iy)
    if d == 180:
        return (ix - LANE_OFFSET, iy)
    if d == 90:
        return (ix, iy - LANE_OFFSET)
    if d == 270:
        return (ix, iy + LANE_OFFSET)
    return (ix, iy)


# ──────────────────────── Route Building ────────────────────────
ROUTE_COOLDOWN = 4.0
PERIMETER_SPAWN_OFFSET = 30.0


def _build_straight_route(axis, coord, direction):
    """Straight route through an entire column or row, edge to edge."""
    if axis == "col":
        col_x = coord
        if direction == 180.0:
            lane_x = col_x - LANE_OFFSET
            ys = sorted(set(y for x, y in INTERSECTIONS if x == col_x), reverse=True)
            wps = [(lane_x, ys[0] + PERIMETER_SPAWN_OFFSET)]
            for y in ys:
                wps.append((lane_x, y))
            wps.append((lane_x, ys[-1] - PERIMETER_SPAWN_OFFSET))
        else:
            lane_x = col_x + LANE_OFFSET
            ys = sorted(set(y for x, y in INTERSECTIONS if x == col_x))
            wps = [(lane_x, ys[0] - PERIMETER_SPAWN_OFFSET)]
            for y in ys:
                wps.append((lane_x, y))
            wps.append((lane_x, ys[-1] + PERIMETER_SPAWN_OFFSET))
    else:
        row_y = coord
        if direction == 90.0:
            lane_y = row_y - LANE_OFFSET
            xs = sorted(set(x for x, y in INTERSECTIONS if y == row_y))
            wps = [(xs[0] - PERIMETER_SPAWN_OFFSET, lane_y)]
            for x in xs:
                wps.append((x, lane_y))
            wps.append((xs[-1] + PERIMETER_SPAWN_OFFSET, lane_y))
        else:
            lane_y = row_y + LANE_OFFSET
            xs = sorted(set(x for x, y in INTERSECTIONS if y == row_y), reverse=True)
            wps = [(xs[0] + PERIMETER_SPAWN_OFFSET, lane_y)]
            for x in xs:
                wps.append((x, lane_y))
            wps.append((xs[-1] - PERIMETER_SPAWN_OFFSET, lane_y))
    return wps, direction


def _build_turn_route(entry_edge, entry_idx, turn_intersection, exit_dir):
    """Build an L-shaped route: enter from a grid edge, turn at an intersection, exit."""
    turn_ix, turn_iy = turn_intersection
    wps = []

    if entry_edge == "top":
        entry_dir = 180.0
        col_x = _ALL_COL_X[entry_idx]
        lane_x = col_x - LANE_OFFSET
        wps.append((lane_x, _MAX_Y + PERIMETER_SPAWN_OFFSET))
        ys_entry = sorted([y for x, y in INTERSECTIONS if x == col_x and y >= turn_iy], reverse=True)
        for y in ys_entry:
            wps.append((lane_x, y))
    elif entry_edge == "bottom":
        entry_dir = 0.0
        col_x = _ALL_COL_X[entry_idx]
        lane_x = col_x + LANE_OFFSET
        wps.append((lane_x, _MIN_Y - PERIMETER_SPAWN_OFFSET))
        ys_entry = sorted([y for x, y in INTERSECTIONS if x == col_x and y <= turn_iy])
        for y in ys_entry:
            wps.append((lane_x, y))
    elif entry_edge == "left":
        entry_dir = 90.0
        row_y = _ALL_ROW_Y[entry_idx]
        lane_y = row_y - LANE_OFFSET
        wps.append((_MIN_X - PERIMETER_SPAWN_OFFSET, lane_y))
        xs_entry = sorted([x for x, y in INTERSECTIONS if y == row_y and x <= turn_ix])
        for x in xs_entry:
            wps.append((x, lane_y))
    elif entry_edge == "right":
        entry_dir = 270.0
        row_y = _ALL_ROW_Y[entry_idx]
        lane_y = row_y + LANE_OFFSET
        wps.append((_MAX_X + PERIMETER_SPAWN_OFFSET, lane_y))
        xs_entry = sorted([x for x, y in INTERSECTIONS if y == row_y and x >= turn_ix], reverse=True)
        for x in xs_entry:
            wps.append((x, lane_y))
    else:
        return [], 0.0

    # Turn waypoint
    turn_wp = _lane_xy(turn_ix, turn_iy, exit_dir)
    wps.append(turn_wp)

    # Exit leg
    if exit_dir == 0.0:
        lane_x = turn_ix + LANE_OFFSET
        exits = sorted([y for x, y in INTERSECTIONS if x == turn_ix and y > turn_iy])
        for y in exits:
            wps.append((lane_x, y))
        wps.append((lane_x, _MAX_Y + PERIMETER_SPAWN_OFFSET))
    elif exit_dir == 180.0:
        lane_x = turn_ix - LANE_OFFSET
        exits = sorted([y for x, y in INTERSECTIONS if x == turn_ix and y < turn_iy], reverse=True)
        for y in exits:
            wps.append((lane_x, y))
        wps.append((lane_x, _MIN_Y - PERIMETER_SPAWN_OFFSET))
    elif exit_dir == 90.0:
        lane_y = turn_iy - LANE_OFFSET
        exits = sorted([x for x, y in INTERSECTIONS if y == turn_iy and x > turn_ix])
        for x in exits:
            wps.append((x, lane_y))
        wps.append((_MAX_X + PERIMETER_SPAWN_OFFSET, lane_y))
    elif exit_dir == 270.0:
        lane_y = turn_iy + LANE_OFFSET
        exits = sorted([x for x, y in INTERSECTIONS if y == turn_iy and x < turn_ix], reverse=True)
        for x in exits:
            wps.append((x, lane_y))
        wps.append((_MIN_X - PERIMETER_SPAWN_OFFSET, lane_y))

    return wps, entry_dir


# ──────────────────────── Route Catalogue ────────────────────────

_ALL_ROUTE_KEYS = []

# Straight routes (edge to edge)
for cx in _ALL_COL_X:
    _ALL_ROUTE_KEYS.append(("straight", "col", cx, 180.0))
    _ALL_ROUTE_KEYS.append(("straight", "col", cx, 0.0))
for ry in _ALL_ROW_Y:
    _ALL_ROUTE_KEYS.append(("straight", "row", ry, 90.0))
    _ALL_ROUTE_KEYS.append(("straight", "row", ry, 270.0))

# Turn routes at interior intersections
for ix, iy in INTERSECTIONS:
    if abs(ix) < 1 and abs(iy) < 1:
        continue  # skip demo center

    col_idx = _ALL_COL_X.index(ix) if ix in _ALL_COL_X else -1
    row_idx = _ALL_ROW_Y.index(iy) if iy in _ALL_ROW_Y else -1
    if col_idx < 0 or row_idx < 0:
        continue

    # Enter from top (south), turn east/west
    _ALL_ROUTE_KEYS.append(("turn", "top", col_idx, (ix, iy), 90.0))
    _ALL_ROUTE_KEYS.append(("turn", "top", col_idx, (ix, iy), 270.0))
    # Enter from bottom (north), turn east/west
    _ALL_ROUTE_KEYS.append(("turn", "bottom", col_idx, (ix, iy), 90.0))
    _ALL_ROUTE_KEYS.append(("turn", "bottom", col_idx, (ix, iy), 270.0))
    # Enter from left (east), turn north/south
    _ALL_ROUTE_KEYS.append(("turn", "left", row_idx, (ix, iy), 0.0))
    _ALL_ROUTE_KEYS.append(("turn", "left", row_idx, (ix, iy), 180.0))
    # Enter from right (west), turn north/south
    _ALL_ROUTE_KEYS.append(("turn", "right", row_idx, (ix, iy), 0.0))
    _ALL_ROUTE_KEYS.append(("turn", "right", row_idx, (ix, iy), 180.0))


def _build_route(route_key) -> Tuple[List[Tuple[float, float]], float]:
    rtype = route_key[0]
    if rtype == "straight":
        _, axis, coord, direction = route_key
        return _build_straight_route(axis, coord, direction)
    elif rtype == "turn":
        _, edge, idx, intersection, exit_dir = route_key
        return _build_turn_route(edge, idx, intersection, exit_dir)
    return [], 0.0


# ──────────────────────── Background Traffic Manager ────────────────────────

class BackgroundTrafficManager:
    def __init__(self):
        self._vehicles: Dict[str, VehicleAgent] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._counter = 0
        self._lock = threading.Lock()
        self._traffic_lights: List[GridTrafficLight] = [
            GridTrafficLight(x, y) for x, y in TRAFFIC_LIGHT_INTERSECTIONS
        ]
        self._tl_thread: Optional[threading.Thread] = None
        self._route_cooldowns: Dict = {}

    @property
    def active(self) -> bool:
        return self._running

    def get_traffic_light_states(self) -> List[dict]:
        return [tl.to_dict() for tl in self._traffic_lights]

    def get_traffic_light_for(self, x: float, y: float) -> Optional[GridTrafficLight]:
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
        all_states = channel.get_all_states()
        for msg in all_states.values():
            if msg.agent_type != "vehicle":
                continue
            d = math.sqrt((msg.x - start_x) ** 2 + (msg.y - start_y) ** 2)
            if d < MIN_SPAWN_DISTANCE:
                angle_diff = abs(msg.direction - direction) % 360
                if angle_diff < 30 or angle_diff > 330:
                    return True
        return False

    def _spawn_vehicle(self):
        now = time.time()

        def _cooldown_key(rk):
            return str(rk)

        available = [
            rk for rk in _ALL_ROUTE_KEYS
            if now - self._route_cooldowns.get(_cooldown_key(rk), 0) >= ROUTE_COOLDOWN
        ]

        if not available:
            return

        random.shuffle(available)
        for route_key in available:
            waypoints, direction = _build_route(route_key)
            if len(waypoints) < 2:
                continue
            start_x, start_y = waypoints[0]
            if not self._is_spawn_blocked(start_x, start_y, direction):
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
                    target_speed=speed if not is_emergency else min(speed * 1.4, 25.0),
                    intention="straight",
                    is_emergency=is_emergency,
                    waypoints=waypoints[1:],
                )

                with self._lock:
                    self._vehicles[agent_id] = vehicle

                self._route_cooldowns[_cooldown_key(route_key)] = now

                vehicle.start()
                etype = " [EMERGENCY]" if is_emergency else ""
                logger.debug(f"Spawned {agent_id}{etype} at ({start_x:.0f}, {start_y:.0f}) dir={direction}")
                return

    def get_vehicle_count(self) -> int:
        with self._lock:
            return len(self._vehicles)


bg_traffic = BackgroundTrafficManager()

