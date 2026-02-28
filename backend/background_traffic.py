"""
background_traffic.py — Manager pentru trafic ambient pe grila de intersectii.
Genereaza masini cu trasee variate (drept, viraj stanga/dreapta) prin oras.
Drumurile formeaza un patrat inchis — toate capetele sunt unite, nimic nu duce in gol.
Masinile sunt persistente — nu dispar, cand ajung la marginea hartii fac stanga sau dreapta.
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
#c
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

# Background traffic settings
NUM_BG_VEHICLES = 25          # fixed number of persistent vehicles
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


def _snap_to_lane(x, y, direction):
    """Snap a position to the correct lane for the given direction.
    This ensures vehicles stay exactly on their lane after a turn.
    """
    d = direction % 360
    # Find nearest intersection axis
    nearest_col = min(_ALL_COL_X, key=lambda cx: abs(cx - x))
    nearest_row = min(_ALL_ROW_Y, key=lambda ry: abs(ry - y))
    if d == 0:    # heading north, lane = col + OFFSET
        return (nearest_col + LANE_OFFSET, y)
    if d == 180:  # heading south, lane = col - OFFSET
        return (nearest_col - LANE_OFFSET, y)
    if d == 90:   # heading east, lane = row - OFFSET
        return (x, nearest_row - LANE_OFFSET)
    if d == 270:  # heading west, lane = row + OFFSET
        return (x, nearest_row + LANE_OFFSET)
    return (x, y)


# ──────────────────────── Continuation Waypoints ────────────────────────
# When a vehicle reaches the edge of the map and can't go forward,
# it turns left or right and continues driving. No despawning.

def generate_continuation_waypoints(x, y, current_direction):
    """Generate new waypoints for a vehicle that reached the grid edge.
    The vehicle turns left or right (randomly) onto a perpendicular road
    and drives to the other edge. Returns (waypoints, new_direction).
    """
    d = current_direction % 360

    # Determine which edge we're at and pick perpendicular directions
    if d == 0:    # was heading north, now at top edge
        options = [90.0, 270.0]   # turn east or west
    elif d == 180:  # was heading south, now at bottom edge
        options = [90.0, 270.0]
    elif d == 90:   # was heading east, now at right edge
        options = [0.0, 180.0]    # turn north or south
    elif d == 270:  # was heading west, now at left edge
        options = [0.0, 180.0]
    else:
        options = [0.0, 90.0, 180.0, 270.0]

    new_dir = random.choice(options)

    # Find the nearest intersection to snap the turn onto
    nearest_col = min(_ALL_COL_X, key=lambda cx: abs(cx - x))
    nearest_row = min(_ALL_ROW_Y, key=lambda ry: abs(ry - y))

    # Determine turn intersection based on where we are
    if d in (0, 180):   # was on a column, turn onto a row
        turn_ix = nearest_col
        # Pick the row we're closest to (should be at edge)
        turn_iy = nearest_row
    else:              # was on a row, turn onto a column
        turn_ix = nearest_col
        turn_iy = nearest_row

    wps = []

    # Add turn waypoint (snap to correct lane for new direction)
    turn_wp = _lane_xy(turn_ix, turn_iy, new_dir)
    wps.append(turn_wp)

    # Add waypoints along the new direction until the opposite edge
    if new_dir == 0.0:    # heading north
        lane_x = turn_ix + LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == turn_ix and y2 > turn_iy])
        for iy in ys:
            wps.append((lane_x, iy))
    elif new_dir == 180.0:  # heading south
        lane_x = turn_ix - LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == turn_ix and y2 < turn_iy], reverse=True)
        for iy in ys:
            wps.append((lane_x, iy))
    elif new_dir == 90.0:   # heading east
        lane_y = turn_iy - LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == turn_iy and x2 > turn_ix])
        for ix in xs:
            wps.append((ix, lane_y))
    elif new_dir == 270.0:  # heading west
        lane_y = turn_iy + LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == turn_iy and x2 < turn_ix], reverse=True)
        for ix in xs:
            wps.append((ix, lane_y))

    return wps, new_dir


def generate_random_turn_at_intersection(x, y, current_direction):
    """At any intersection, optionally generate turn waypoints.
    Returns (waypoints, new_direction) or (None, None) if no turn.
    Called by the vehicle at each intersection to decide: straight, left, or right.
    """
    d = current_direction % 360

    # Find nearest intersection
    nearest_col = min(_ALL_COL_X, key=lambda cx: abs(cx - x))
    nearest_row = min(_ALL_ROW_Y, key=lambda ry: abs(ry - y))

    # Only turn if we're actually close to an intersection
    if abs(x - nearest_col) > 20 and abs(y - nearest_row) > 20:
        return None, None

    # Determine available turn directions (perpendicular to current)
    if d in (0.0, 180.0):   # on NS road, can turn EW
        options = [90.0, 270.0]
    else:                     # on EW road, can turn NS
        options = [0.0, 180.0]

    new_dir = random.choice(options)
    turn_ix = nearest_col
    turn_iy = nearest_row

    wps = []
    # Turn waypoint
    turn_wp = _lane_xy(turn_ix, turn_iy, new_dir)
    wps.append(turn_wp)

    # Continue straight along new direction to the edge
    if new_dir == 0.0:
        lane_x = turn_ix + LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == turn_ix and y2 > turn_iy])
        for iy in ys:
            wps.append((lane_x, iy))
    elif new_dir == 180.0:
        lane_x = turn_ix - LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == turn_ix and y2 < turn_iy], reverse=True)
        for iy in ys:
            wps.append((lane_x, iy))
    elif new_dir == 90.0:
        lane_y = turn_iy - LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == turn_iy and x2 > turn_ix])
        for ix in xs:
            wps.append((ix, lane_y))
    elif new_dir == 270.0:
        lane_y = turn_iy + LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == turn_iy and x2 < turn_ix], reverse=True)
        for ix in xs:
            wps.append((ix, lane_y))

    return wps, new_dir


# ──────────────────────── Initial Route Building ────────────────────────

def _build_initial_route_from_intersection(ix, iy, direction):
    """Build a route starting from an intersection going in direction to the edge."""
    wps = []
    start_wp = _lane_xy(ix, iy, direction)
    wps.append(start_wp)

    if direction == 0.0:
        lane_x = ix + LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == ix and y2 > iy])
        for y2 in ys:
            wps.append((lane_x, y2))
    elif direction == 180.0:
        lane_x = ix - LANE_OFFSET
        ys = sorted([y2 for x2, y2 in INTERSECTIONS if x2 == ix and y2 < iy], reverse=True)
        for y2 in ys:
            wps.append((lane_x, y2))
    elif direction == 90.0:
        lane_y = iy - LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == iy and x2 > ix])
        for x2 in xs:
            wps.append((x2, lane_y))
    elif direction == 270.0:
        lane_y = iy + LANE_OFFSET
        xs = sorted([x2 for x2, y2 in INTERSECTIONS if y2 == iy and x2 < ix], reverse=True)
        for x2 in xs:
            wps.append((x2, lane_y))

    return wps


# Keep _ALL_ROUTE_KEYS and _build_route for drunk driver spawning
_ALL_ROUTE_KEYS = []
for cx in _ALL_COL_X:
    _ALL_ROUTE_KEYS.append(("straight", "col", cx, 180.0))
    _ALL_ROUTE_KEYS.append(("straight", "col", cx, 0.0))
for ry in _ALL_ROW_Y:
    _ALL_ROUTE_KEYS.append(("straight", "row", ry, 90.0))
    _ALL_ROUTE_KEYS.append(("straight", "row", ry, 270.0))


def _build_straight_route(axis, coord, direction):
    """Straight route through an entire column or row, edge to edge."""
    if axis == "col":
        col_x = coord
        if direction == 180.0:
            lane_x = col_x - LANE_OFFSET
            ys = sorted(set(y for x, y in INTERSECTIONS if x == col_x), reverse=True)
            wps = [(lane_x, ys[0])]
            for y in ys[1:]:
                wps.append((lane_x, y))
        else:
            lane_x = col_x + LANE_OFFSET
            ys = sorted(set(y for x, y in INTERSECTIONS if x == col_x))
            wps = [(lane_x, ys[0])]
            for y in ys[1:]:
                wps.append((lane_x, y))
    else:
        row_y = coord
        if direction == 90.0:
            lane_y = row_y - LANE_OFFSET
            xs = sorted(set(x for x, y in INTERSECTIONS if y == row_y))
            wps = [(xs[0], lane_y)]
            for x in xs[1:]:
                wps.append((x, lane_y))
        else:
            lane_y = row_y + LANE_OFFSET
            xs = sorted(set(x for x, y in INTERSECTIONS if y == row_y), reverse=True)
            wps = [(xs[0], lane_y)]
            for x in xs[1:]:
                wps.append((x, lane_y))
    return wps, direction


def _build_route(route_key) -> Tuple[List[Tuple[float, float]], float]:
    rtype = route_key[0]
    if rtype == "straight":
        _, axis, coord, direction = route_key
        return _build_straight_route(axis, coord, direction)
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
        self._spawned = False  # only spawn once

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
        # Spawn all vehicles at once on first start
        if not self._spawned:
            self._spawn_all_vehicles()
            self._spawned = True
        else:
            # Re-start existing vehicles that were stopped
            with self._lock:
                for v in self._vehicles.values():
                    if not v._running:
                        v.start()
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
        self._spawned = False
        logger.info("Background traffic stopped")

    def _tl_loop(self):
        dt = 0.2
        while self._running:
            for tl in self._traffic_lights:
                tl.update(dt)
            time.sleep(dt)

    def _is_spawn_blocked(self, start_x: float, start_y: float) -> bool:
        """Check if another vehicle is too close to the spawn point."""
        with self._lock:
            for v in self._vehicles.values():
                d = math.sqrt((v.x - start_x) ** 2 + (v.y - start_y) ** 2)
                if d < MIN_SPAWN_DISTANCE:
                    return True
        return False

    def _spawn_all_vehicles(self):
        """Spawn NUM_BG_VEHICLES persistent vehicles spread across the grid."""
        # Collect all valid spawn positions: every intersection + direction combo
        spawn_options = []
        for ix, iy in INTERSECTIONS:
            # Skip demo center
            if abs(ix) < 1 and abs(iy) < 1:
                continue
            for d in [0.0, 90.0, 180.0, 270.0]:
                lx, ly = _lane_xy(ix, iy, d)
                spawn_options.append((lx, ly, d, ix, iy))

        random.shuffle(spawn_options)

        spawned = 0
        for lx, ly, direction, ix, iy in spawn_options:
            if spawned >= NUM_BG_VEHICLES:
                break
            if self._is_spawn_blocked(lx, ly):
                continue

            speed = random.uniform(BG_SPEED_MIN, BG_SPEED_MAX)
            is_emergency = random.random() < EMERGENCY_CHANCE

            self._counter += 1
            agent_id = f"BG_{self._counter:03d}"

            # Build initial waypoints from this intersection to the edge
            initial_wps = _build_initial_route_from_intersection(ix, iy, direction)
            # Remove the first waypoint (it's the spawn position itself)
            route_wps = initial_wps[1:] if len(initial_wps) > 1 else []

            vehicle = VehicleAgent(
                agent_id=agent_id,
                start_x=lx,
                start_y=ly,
                direction=direction,
                initial_speed=speed,
                target_speed=speed if not is_emergency else min(speed * 1.4, 25.0),
                intention="straight",
                is_emergency=is_emergency,
                waypoints=route_wps,
                persistent=True,   # never despawn
            )

            with self._lock:
                self._vehicles[agent_id] = vehicle

            vehicle.start()
            spawned += 1
            etype = " [EMERGENCY]" if is_emergency else ""
            logger.debug(f"Spawned {agent_id}{etype} at ({lx:.0f}, {ly:.0f}) dir={direction}")

        logger.info(f"Spawned {spawned} persistent background vehicles")

    def get_vehicle_count(self) -> int:
        with self._lock:
            return len(self._vehicles)


bg_traffic = BackgroundTrafficManager()
