"""
priority_negotiation.py — Negociere prioritate la intersectie.
"""

import math
from typing import Dict, Tuple
from v2x_channel import V2XMessage
from collision_detector import time_to_intersection, distance, INTERSECTION_CENTER, INTERSECTION_RADIUS

STOP_LINE_DISTANCE = INTERSECTION_RADIUS


def _dist_to_stop_line(agent: V2XMessage) -> float:
    """Distanta pe axa de miscare pana la marginea patratului intersectiei."""
    rad = math.radians(agent.direction)
    vx = math.sin(rad)
    vy = math.cos(rad)
    if abs(vy) >= abs(vx):
        return max(0.0, abs(agent.y) - STOP_LINE_DISTANCE)
    else:
        return max(0.0, abs(agent.x) - STOP_LINE_DISTANCE)


def _is_inside_box(agent: V2XMessage) -> bool:
    """Verifica daca vehiculul e in interiorul patratului intersectiei."""
    return abs(agent.x) < STOP_LINE_DISTANCE and abs(agent.y) < STOP_LINE_DISTANCE


def get_approach_direction(agent: V2XMessage) -> str:
    cx, cy = INTERSECTION_CENTER
    dx = agent.x - cx
    dy = agent.y - cy
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    else:
        return "north" if dy > 0 else "south"


def is_on_right(my_direction: str, other_direction: str) -> bool:
    right_map = {
        "north": "east",
        "east":  "south",
        "south": "west",
        "west":  "north",
    }
    return right_map.get(my_direction) == other_direction


def resolve_priority(agent1: V2XMessage, agent2: V2XMessage) -> Tuple[str, str, str]:
    if agent1.is_emergency and not agent2.is_emergency:
        return "go", "stop", "emergency_vehicle"
    if agent2.is_emergency and not agent1.is_emergency:
        return "stop", "go", "emergency_vehicle"

    t1 = time_to_intersection(agent1)
    t2 = time_to_intersection(agent2)
    time_diff = abs(t1 - t2)

    if time_diff > 2.0:
        if t1 < t2:
            return "go", "yield", "first_arrival"
        else:
            return "yield", "go", "first_arrival"

    dir1 = get_approach_direction(agent1)
    dir2 = get_approach_direction(agent2)

    if is_on_right(dir1, dir2):
        return "yield", "go", "right_of_way"
    elif is_on_right(dir2, dir1):
        return "go", "yield", "right_of_way"

    if agent1.speed < agent2.speed:
        return "yield", "go", "lower_speed_yields"
    elif agent2.speed < agent1.speed:
        return "go", "yield", "lower_speed_yields"

    if agent1.agent_id < agent2.agent_id:
        return "go", "yield", "id_tiebreak"
    else:
        return "yield", "go", "id_tiebreak"


def compute_decisions_for_all(all_agents: Dict[str, V2XMessage]) -> Dict[str, dict]:
    from collision_detector import assess_intersection_risk

    decisions = {}
    for agent_id in all_agents:
        decisions[agent_id] = {"decision": "go", "reason": "clear", "priority_score": 0}

    agents_list = [a for a in all_agents.values() if a.agent_type == "vehicle"]
    priority_order = {"go": 0, "yield": 1, "brake": 2, "stop": 3}

    for i in range(len(agents_list)):
        for j in range(i + 1, len(agents_list)):
            a1 = agents_list[i]
            a2 = agents_list[j]
            risk = assess_intersection_risk(a1, a2)

            if risk in ("high", "collision"):
                dec1, dec2, reason = resolve_priority(a1, a2)

                if priority_order.get(dec1, 0) > priority_order.get(decisions[a1.agent_id]["decision"], 0):
                    decisions[a1.agent_id] = {"decision": dec1, "reason": reason, "priority_score": i}

                if priority_order.get(dec2, 0) > priority_order.get(decisions[a2.agent_id]["decision"], 0):
                    decisions[a2.agent_id] = {"decision": dec2, "reason": reason, "priority_score": j}

    return decisions


def compute_recommended_speed(agent: V2XMessage, decision: str, target_speed: float = 14.0) -> float:
    inside = _is_inside_box(agent)
    dist_to_edge = _dist_to_stop_line(agent)

    if decision == "go":
        return target_speed

    if inside:
        return target_speed

    if decision == "stop" or dist_to_edge < 3.0:
        return 0.0
    elif decision == "yield":
        factor = min(1.0, dist_to_edge / 40.0)
        return max(2.0, target_speed * factor * 0.5)
    elif decision == "brake":
        factor = min(1.0, dist_to_edge / 40.0)
        return max(0.0, target_speed * factor * 0.3)

    return target_speed
