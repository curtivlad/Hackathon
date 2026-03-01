
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


def test_right_of_way_north_west():
    assert is_on_right("north", "west") is True


def test_right_of_way_north_east():
    assert is_on_right("north", "east") is False


def test_right_of_way_east_north():
    assert is_on_right("east", "north") is True


def test_right_of_way_south_east():
    assert is_on_right("south", "east") is True


def test_right_of_way_west_south():
    assert is_on_right("west", "south") is True


def test_right_of_way_all_false_cases():
    assert is_on_right("north", "north") is False
    assert is_on_right("east", "east") is False
    assert is_on_right("south", "south") is False
    assert is_on_right("west", "west") is False


def test_emergency_always_wins():
    amb = _make_agent("AMB", -50, -10, 14, 90, emergency=True)
    car = _make_agent("CAR", 10, -50, 10, 0, emergency=False)
    d1, d2, reason = resolve_priority(amb, car)
    assert d1 == "go"
    assert d2 == "stop"
    assert reason == "emergency_vehicle"


def test_emergency_reverse():
    car = _make_agent("CAR", -50, -10, 10, 90, emergency=False)
    amb = _make_agent("AMB", 10, -50, 14, 0, emergency=True)
    d1, d2, reason = resolve_priority(car, amb)
    assert d1 == "stop"
    assert d2 == "go"
    assert reason == "emergency_vehicle"


def test_both_emergency():
    a1 = _make_agent("AMB1", -50, -10, 14, 90, emergency=True)
    a2 = _make_agent("AMB2", 10, -50, 14, 0, emergency=True)
    d1, d2, reason = resolve_priority(a1, a2)
    assert d1 in ("go", "yield")
    assert d2 in ("go", "yield")
    assert d1 != d2


def test_right_of_way_resolution():
    vh_n = _make_agent("VH_N", -10, 120, 10, 180)
    vh_w = _make_agent("VH_W", -120, -10, 10, 90)
    d1, d2, reason = resolve_priority(vh_n, vh_w)
    assert d1 == "yield"
    assert d2 == "go"


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
