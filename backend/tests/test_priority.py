"""
test_priority.py — Teste unitare pentru negocierea prioritatii.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v2x_channel import V2XMessage
from priority_negotiation import resolve_priority, is_on_right, get_approach_direction


def _make_agent(aid, x, y, speed, direction, emergency=False):
    return V2XMessage(
        agent_id=aid, agent_type="vehicle",
        x=x, y=y, speed=speed, direction=direction,
        intention="straight", risk_level="low",
        decision="go", is_emergency=emergency,
    )


# ── is_on_right tests ──

def test_right_of_way_north_west():
    """Vehicul din nord: dreapta lui e vestul."""
    assert is_on_right("north", "west") is True


def test_right_of_way_north_east():
    """Vehicul din nord: estul NU e dreapta lui."""
    assert is_on_right("north", "east") is False


def test_right_of_way_east_north():
    """Vehicul din est: dreapta lui e nordul."""
    assert is_on_right("east", "north") is True


def test_right_of_way_south_east():
    """Vehicul din sud: dreapta lui e estul."""
    assert is_on_right("south", "east") is True


def test_right_of_way_west_south():
    """Vehicul din vest: dreapta lui e sudul."""
    assert is_on_right("west", "south") is True


def test_right_of_way_all_false_cases():
    """Niciun caz de 'same direction' nu e din dreapta."""
    assert is_on_right("north", "north") is False
    assert is_on_right("east", "east") is False
    assert is_on_right("south", "south") is False
    assert is_on_right("west", "west") is False


# ── resolve_priority tests ──

def test_emergency_always_wins():
    """Ambulanta are INTOTDEAUNA prioritate."""
    amb = _make_agent("AMB", -50, -10, 14, 90, emergency=True)
    car = _make_agent("CAR", 10, -50, 10, 0, emergency=False)
    d1, d2, reason = resolve_priority(amb, car)
    assert d1 == "go"
    assert d2 == "stop"
    assert reason == "emergency_vehicle"


def test_emergency_reverse():
    """Daca al doilea e ambulanta, el castiga."""
    car = _make_agent("CAR", -50, -10, 10, 90, emergency=False)
    amb = _make_agent("AMB", 10, -50, 14, 0, emergency=True)
    d1, d2, reason = resolve_priority(car, amb)
    assert d1 == "stop"
    assert d2 == "go"
    assert reason == "emergency_vehicle"


def test_both_emergency():
    """Doua ambulante — se folosesc regulile normale."""
    a1 = _make_agent("AMB1", -50, -10, 14, 90, emergency=True)
    a2 = _make_agent("AMB2", 10, -50, 14, 0, emergency=True)
    d1, d2, reason = resolve_priority(a1, a2)
    # Both emergency — falls through to normal rules
    assert d1 in ("go", "yield")
    assert d2 in ("go", "yield")
    assert d1 != d2  # one goes, one yields


def test_right_of_way_resolution():
    """Vehicul din nord cedeaza celui din vest (din dreapta)."""
    # VH_N vine din nord (y=120, dir=180), VH_W vine din vest (x=-120, dir=90)
    vh_n = _make_agent("VH_N", -10, 120, 10, 180)
    vh_w = _make_agent("VH_W", -120, -10, 10, 90)
    d1, d2, reason = resolve_priority(vh_n, vh_w)
    # VH_N approach = "north", VH_W approach = "west"
    # is_on_right("north", "west") => True => VH_N yields
    assert d1 == "yield"
    assert d2 == "go"


# ── get_approach_direction tests ──

def test_approach_from_north():
    agent = _make_agent("A", 0, 100, 10, 180)
    assert get_approach_direction(agent) == "north"


def test_approach_from_south():
    agent = _make_agent("A", 0, -100, 10, 0)
    assert get_approach_direction(agent) == "south"


def test_approach_from_east():
    agent = _make_agent("A", 100, 0, 10, 270)
    assert get_approach_direction(agent) == "east"


def test_approach_from_west():
    agent = _make_agent("A", -100, 0, 10, 90)
    assert get_approach_direction(agent) == "west"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

