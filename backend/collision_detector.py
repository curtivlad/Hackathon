
import math
from typing import Dict, Tuple
from v2x_channel import V2XMessage

INTERSECTION_CENTER = (0.0, 0.0)
INTERSECTION_RADIUS = 30.0
DANGER_ZONE_RADIUS = 120.0

TTC_COLLISION = 3.0
TTC_HIGH = 6.0
TTC_MEDIUM = 10.0


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def get_velocity_components(speed: float, direction: float) -> Tuple[float, float]:
    rad = math.radians(direction)
    vx = speed * math.sin(rad)
    vy = speed * math.cos(rad)
    return vx, vy


def time_to_intersection(agent: V2XMessage) -> float:
    cx, cy = INTERSECTION_CENTER
    dist = distance(agent.x, agent.y, cx, cy)

    if agent.speed < 0.1:
        return float('inf')

    vx, vy = get_velocity_components(agent.speed, agent.direction)
    dx = cx - agent.x
    dy = cy - agent.y
    dot = (vx * dx + vy * dy) / (dist + 1e-9)

    if dot <= 0:
        return float('inf')

    return dist / dot


def compute_ttc(agent1: V2XMessage, agent2: V2XMessage) -> float:
    dx = agent2.x - agent1.x
    dy = agent2.y - agent1.y
    dist = math.sqrt(dx ** 2 + dy ** 2)

    if dist < 1.0:
        return 0.0

    v1x, v1y = get_velocity_components(agent1.speed, agent1.direction)
    v2x, v2y = get_velocity_components(agent2.speed, agent2.direction)

    rvx = v2x - v1x
    rvy = v2y - v1y
    relative_speed = math.sqrt(rvx ** 2 + rvy ** 2)

    if relative_speed < 0.1:
        return float('inf')

    dot = (dx * rvx + dy * rvy) / dist

    if dot >= 0:
        return float('inf')

    return dist / (-dot)


def _are_on_same_road_opposite_dirs(a1: V2XMessage, a2: V2XMessage) -> bool:
    r1 = math.radians(a1.direction)
    r2 = math.radians(a2.direction)
    ax1 = "NS" if abs(math.cos(r1)) >= abs(math.sin(r1)) else "EW"
    ax2 = "NS" if abs(math.cos(r2)) >= abs(math.sin(r2)) else "EW"
    if ax1 != ax2:
        return False
    angle_diff = abs(a1.direction - a2.direction) % 360
    return abs(angle_diff - 180) < 10


def _are_following_same_direction(a1: V2XMessage, a2: V2XMessage) -> bool:
    r1 = math.radians(a1.direction)
    r2 = math.radians(a2.direction)
    ax1 = "NS" if abs(math.cos(r1)) >= abs(math.sin(r1)) else "EW"
    ax2 = "NS" if abs(math.cos(r2)) >= abs(math.sin(r2)) else "EW"
    if ax1 != ax2:
        return False
    angle_diff = abs(a1.direction - a2.direction) % 360
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    if angle_diff > 30:
        return False
    if ax1 == "NS":
        return abs(a1.x - a2.x) < 25.0
    else:
        return abs(a1.y - a2.y) < 25.0


def assess_intersection_risk(agent1: V2XMessage, agent2: V2XMessage) -> str:
    if _are_on_same_road_opposite_dirs(agent1, agent2):
        return "low"
    if _are_following_same_direction(agent1, agent2):
        return "low"

    t1 = time_to_intersection(agent1)
    t2 = time_to_intersection(agent2)

    if t1 == float('inf') or t2 == float('inf'):
        return "low"

    delta_t = abs(t1 - t2)
    dist = distance(agent1.x, agent1.y, agent2.x, agent2.y)
    ttc = compute_ttc(agent1, agent2)

    if ttc <= TTC_COLLISION or (delta_t < 2.0 and dist < DANGER_ZONE_RADIUS):
        return "collision"
    elif ttc <= TTC_HIGH or (delta_t < 4.0 and dist < DANGER_ZONE_RADIUS):
        return "high"
    elif ttc <= TTC_MEDIUM or delta_t < 6.0:
        return "medium"
    else:
        return "low"


def compute_risk_for_agent(my_agent: V2XMessage, others: Dict[str, V2XMessage]) -> str:
    if not others:
        return "low"

    dist_to_center = distance(my_agent.x, my_agent.y, *INTERSECTION_CENTER)
    if dist_to_center > DANGER_ZONE_RADIUS * 2:
        return "low"

    risk_levels = ["low", "medium", "high", "collision"]
    max_risk = "low"

    for other_id, other_agent in others.items():
        risk = assess_intersection_risk(my_agent, other_agent)
        if risk_levels.index(risk) > risk_levels.index(max_risk):
            max_risk = risk
        if max_risk == "collision":
            break

    return max_risk


def get_collision_pairs(all_agents: Dict[str, V2XMessage]) -> list:
    agents = list(all_agents.values())
    pairs = []

    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            a1 = agents[i]
            a2 = agents[j]
            risk = assess_intersection_risk(a1, a2)
            if risk in ("high", "collision"):
                pairs.append({
                    "agent1": a1.agent_id,
                    "agent2": a2.agent_id,
                    "risk": risk,
                    "ttc": round(compute_ttc(a1, a2), 2),
                })

    return pairs
