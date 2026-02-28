"""
collision_detector.py
Detecteaza riscul de coliziune intre agenti folosind Time-To-Collision (TTC).
Fiecare agent isi calculeaza riscul in raport cu ceilalti agenti de pe canal.
"""

import math
from typing import Dict, Tuple
from v2x_channel import V2XMessage


# Zona de intersectie — centrul si raza de risc (metri)
INTERSECTION_CENTER = (0.0, 0.0)
INTERSECTION_RADIUS = 30.0       # daca esti in aceasta raza, esti "in intersectie"
DANGER_ZONE_RADIUS = 60.0        # daca esti in aceasta raza, incepi sa verifici riscul

# Praguri TTC (secunde)
TTC_COLLISION = 2.0   # sub 2s = risc de coliziune iminent
TTC_HIGH = 4.0        # sub 4s = risc ridicat
TTC_MEDIUM = 7.0      # sub 7s = risc mediu


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distanta euclidiana intre doua puncte."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def get_velocity_components(speed: float, direction: float) -> Tuple[float, float]:
    """
    Transforma viteza + directie (grade) in componente (vx, vy).
    Conventie: 0=Nord(+Y), 90=Est(+X), 180=Sud(-Y), 270=Vest(-X)
    """
    rad = math.radians(direction)
    vx = speed * math.sin(rad)
    vy = speed * math.cos(rad)
    return vx, vy


def time_to_intersection(agent: V2XMessage) -> float:
    """
    Calculeaza in cat timp ajunge agentul la centrul intersectiei.
    Returneaza inf daca agentul este stationat sau se indeparteaza.
    """
    cx, cy = INTERSECTION_CENTER
    dist = distance(agent.x, agent.y, cx, cy)

    if agent.speed < 0.1:
        return float('inf')

    vx, vy = get_velocity_components(agent.speed, agent.direction)

    # Proiectia vitezei pe directia spre centru
    dx = cx - agent.x
    dy = cy - agent.y
    dot = (vx * dx + vy * dy) / (dist + 1e-9)

    if dot <= 0:
        return float('inf')  # se indeparteaza de intersectie

    return dist / dot


def compute_ttc(agent1: V2XMessage, agent2: V2XMessage) -> float:
    """
    Calculeaza Time-To-Collision intre doi agenti.
    Foloseste pozitia relativa si viteza relativa.
    """
    # Pozitie relativa
    dx = agent2.x - agent1.x
    dy = agent2.y - agent1.y
    dist = math.sqrt(dx ** 2 + dy ** 2)

    if dist < 1.0:
        return 0.0  # deja in coliziune

    # Viteze
    v1x, v1y = get_velocity_components(agent1.speed, agent1.direction)
    v2x, v2y = get_velocity_components(agent2.speed, agent2.direction)

    # Viteza relativa (agent2 relativ la agent1)
    rvx = v2x - v1x
    rvy = v2y - v1y
    relative_speed = math.sqrt(rvx ** 2 + rvy ** 2)

    if relative_speed < 0.1:
        return float('inf')  # viteze aproape identice, nu se apropie

    # Proiectia vitezei relative pe directia dintre agenti
    dot = (dx * rvx + dy * rvy) / dist

    if dot >= 0:
        return float('inf')  # se indeparteaza unul de altul

    return dist / (-dot)


def assess_intersection_risk(agent1: V2XMessage, agent2: V2XMessage) -> str:
    """
    Evalueaza riscul de coliziune la intersectie intre doi agenti.
    Logica: daca ambii agenti ajung la intersectie in intervale apropiate -> risc.
    """
    t1 = time_to_intersection(agent1)
    t2 = time_to_intersection(agent2)

    # Daca niciunul nu se indreapta spre intersectie
    if t1 == float('inf') or t2 == float('inf'):
        return "low"

    # Diferenta de timp la intersectie
    delta_t = abs(t1 - t2)

    # Distanta curenta intre agenti
    dist = distance(agent1.x, agent1.y, agent2.x, agent2.y)

    # TTC direct intre cei doi agenti
    ttc = compute_ttc(agent1, agent2)

    # Evaluare risc
    if ttc <= TTC_COLLISION or (delta_t < 1.5 and dist < INTERSECTION_RADIUS * 2):
        return "collision"
    elif ttc <= TTC_HIGH or (delta_t < 3.0 and dist < DANGER_ZONE_RADIUS):
        return "high"
    elif ttc <= TTC_MEDIUM or delta_t < 5.0:
        return "medium"
    else:
        return "low"


def compute_risk_for_agent(my_agent: V2XMessage, others: Dict[str, V2XMessage]) -> str:
    """
    Calculeaza nivelul maxim de risc al unui agent fata de toti ceilalti.
    """
    if not others:
        return "low"

    # Verifica daca agentul este in zona de pericol
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
            break  # nu mai are rost sa verificam

    return max_risk


def get_collision_pairs(all_agents: Dict[str, V2XMessage]) -> list:
    """
    Returneaza lista de perechi de agenti cu risc ridicat sau de coliziune.
    Folosit de frontend pentru a evidentia zonele de risc.
    """
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