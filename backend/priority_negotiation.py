"""
priority_negotiation.py
Logica prin care agentii rezolva conflictele de prioritate la intersectie.
"""

import math
from typing import Dict, Tuple
from v2x_channel import V2XMessage
from collision_detector import time_to_intersection, distance, INTERSECTION_CENTER


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
    """
    Rezolva conflictul de prioritate intre doi agenti.
    Returneaza: (decizie_agent1, decizie_agent2, motiv)
    """
    # Regula 1: Vehicul de urgenta
    if agent1.is_emergency and not agent2.is_emergency:
        return "go", "stop", "emergency_vehicle"
    if agent2.is_emergency and not agent1.is_emergency:
        return "stop", "go", "emergency_vehicle"

    # Regula 2: Primul sosit
    t1 = time_to_intersection(agent1)
    t2 = time_to_intersection(agent2)
    time_diff = abs(t1 - t2)

    if time_diff > 2.0:
        if t1 < t2:
            return "go", "yield", "first_arrival"
        else:
            return "yield", "go", "first_arrival"

    # Regula 3: Prioritate la dreapta
    dir1 = get_approach_direction(agent1)
    dir2 = get_approach_direction(agent2)

    if is_on_right(dir1, dir2):
        return "yield", "go", "right_of_way"
    elif is_on_right(dir2, dir1):
        return "go", "yield", "right_of_way"

    # Regula 4: Viteza mai mica cedeaza
    if agent1.speed < agent2.speed:
        return "yield", "go", "lower_speed_yields"
    elif agent2.speed < agent1.speed:
        return "go", "yield", "lower_speed_yields"

    # Tie-break dupa ID
    if agent1.agent_id < agent2.agent_id:
        return "go", "yield", "id_tiebreak"
    else:
        return "yield", "go", "id_tiebreak"


def compute_decisions_for_all(all_agents: Dict[str, V2XMessage]) -> Dict[str, dict]:
    """Calculeaza decizia optima pentru fiecare agent."""
    from collision_detector import assess_intersection_risk

    decisions = {}
    for agent_id in all_agents:
        decisions[agent_id] = {"decision": "go", "reason": "clear", "priority_score": 0}

    agents = list(all_agents.values())
    priority_order = {"go": 0, "yield": 1, "brake": 2, "stop": 3}

    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            a1 = agents[i]
            a2 = agents[j]
            risk = assess_intersection_risk(a1, a2)

            if risk in ("high", "collision"):
                dec1, dec2, reason = resolve_priority(a1, a2)

                if priority_order.get(dec1, 0) > priority_order.get(decisions[a1.agent_id]["decision"], 0):
                    decisions[a1.agent_id] = {"decision": dec1, "reason": reason, "priority_score": i}

                if priority_order.get(dec2, 0) > priority_order.get(decisions[a2.agent_id]["decision"], 0):
                    decisions[a2.agent_id] = {"decision": dec2, "reason": reason, "priority_score": j}

    return decisions


def compute_recommended_speed(agent: V2XMessage, decision: str) -> float:
    """Calculeaza viteza recomandata pe baza deciziei."""
    dist_to_center = distance(agent.x, agent.y, *INTERSECTION_CENTER)

    if decision == "go":
        return min(agent.speed, 14.0)
    elif decision == "yield":
        factor = min(1.0, dist_to_center / 40.0)
        return agent.speed * factor * 0.6
    elif decision == "brake":
        return max(0.0, agent.speed * 0.3)
    elif decision == "stop":
        return 0.0
    return agent.speed