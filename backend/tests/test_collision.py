
import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v2x_channel import V2XMessage
from collision_detector import (
    compute_ttc, distance, assess_intersection_risk,
    get_collision_pairs, time_to_intersection,
    _are_on_same_road_opposite_dirs,
)


def _make_agent(aid, x, y, speed, direction, emergency=False):
    return V2XMessage(
        agent_id=aid, agent_type="vehicle",
        x=x, y=y, speed=speed, direction=direction,
        intention="straight", risk_level="low",
        decision="go", is_emergency=emergency,
    )


def test_distance_zero():
    assert distance(0, 0, 0, 0) == 0.0


def test_distance_known():
    assert abs(distance(0, 0, 3, 4) - 5.0) < 0.01


def test_distance_symmetric():
    assert abs(distance(1, 2, 4, 6) - distance(4, 6, 1, 2)) < 0.001


def test_ttc_converging():
    a1 = _make_agent("A", 0, 100, 10, 180)
    a2 = _make_agent("B", 100, 0, 10, 270)
    ttc = compute_ttc(a1, a2)
    assert ttc > 0
    assert ttc < 100


def test_ttc_diverging():
    a1 = _make_agent("A", 0, 100, 10, 0)
    a2 = _make_agent("B", 100, 0, 10, 90)
    ttc = compute_ttc(a1, a2)
    assert ttc == float('inf')


def test_ttc_stationary():
    a1 = _make_agent("A", 0, 100, 0, 180)
    a2 = _make_agent("B", 100, 0, 10, 270)
    ttc = compute_ttc(a1, a2)
    assert ttc >= 0


def test_ttc_same_position():
    a1 = _make_agent("A", 50, 50, 10, 180)
    a2 = _make_agent("B", 50, 50, 10, 270)
    ttc = compute_ttc(a1, a2)
    assert ttc == 0.0


def test_risk_same_road_opposite():
    a1 = _make_agent("A", 10, 100, 10, 180)
    a2 = _make_agent("B", -10, -100, 10, 0)
    assert _are_on_same_road_opposite_dirs(a1, a2) is True
    assert assess_intersection_risk(a1, a2) == "low"


def test_risk_perpendicular_collision():
    a1 = _make_agent("A", 0, 50, 10, 180)
    a2 = _make_agent("B", 50, 0, 10, 270)
    risk = assess_intersection_risk(a1, a2)
    assert risk in ("high", "collision")


def test_risk_far_away():
    a1 = _make_agent("A", 0, 500, 10, 0)
    a2 = _make_agent("B", 500, 0, 10, 90)
    risk = assess_intersection_risk(a1, a2)
    assert risk == "low"


def test_collision_pairs_empty():
    pairs = get_collision_pairs({})
    assert pairs == []


def test_collision_pairs_single():
    a1 = _make_agent("A", 0, 100, 10, 180)
    pairs = get_collision_pairs({"A": a1})
    assert pairs == []


def test_collision_pairs_no_risk():
    a1 = _make_agent("A", 0, 500, 10, 180)
    a2 = _make_agent("B", 500, 0, 10, 270)
    pairs = get_collision_pairs({"A": a1, "B": a2})
    assert len(pairs) == 0


def test_collision_pairs_high_risk():
    a1 = _make_agent("A", -10, 45, 10, 180)
    a2 = _make_agent("B", 45, -10, 10, 270)
    pairs = get_collision_pairs({"A": a1, "B": a2})
    assert len(pairs) > 0
    assert pairs[0]["risk"] in ("high", "collision")


def test_tti_approaching():
    a = _make_agent("A", 0, 100, 10, 180)
    tti = time_to_intersection(a)
    assert tti > 0
    assert tti < 20


def test_tti_receding():
    a = _make_agent("A", 0, 100, 10, 0)
    tti = time_to_intersection(a)
    assert tti == float('inf')


def test_tti_stationary():
    a = _make_agent("A", 0, 100, 0, 180)
    tti = time_to_intersection(a)
    assert tti == float('inf')


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
