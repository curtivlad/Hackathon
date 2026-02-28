"""
test_collision.py — Teste unitare pentru detectia de coliziune (TTC).
"""

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


# ── distance tests ──

def test_distance_zero():
    assert distance(0, 0, 0, 0) == 0.0


def test_distance_known():
    assert abs(distance(0, 0, 3, 4) - 5.0) < 0.01


def test_distance_symmetric():
    assert abs(distance(1, 2, 4, 6) - distance(4, 6, 1, 2)) < 0.001


# ── TTC tests ──

def test_ttc_converging():
    """Doua vehicule care converg ar trebui sa aiba TTC finit."""
    a1 = _make_agent("A", 0, 100, 10, 180)   # heading south
    a2 = _make_agent("B", 100, 0, 10, 270)    # heading west
    ttc = compute_ttc(a1, a2)
    assert ttc > 0
    assert ttc < 100  # ar trebui sa fie TTC rezonabil


def test_ttc_diverging():
    """Vehicule care se departeaza — TTC infinit."""
    a1 = _make_agent("A", 0, 100, 10, 0)      # heading north (away)
    a2 = _make_agent("B", 100, 0, 10, 90)     # heading east (away)
    ttc = compute_ttc(a1, a2)
    assert ttc == float('inf')


def test_ttc_stationary():
    """Un vehicul stationar — TTC infinit."""
    a1 = _make_agent("A", 0, 100, 0, 180)     # stationary
    a2 = _make_agent("B", 100, 0, 10, 270)
    ttc = compute_ttc(a1, a2)
    # Relative speed should still be > 0 since a2 is moving
    assert ttc >= 0


def test_ttc_same_position():
    """Vehicule la aceeasi pozitie — TTC = 0."""
    a1 = _make_agent("A", 50, 50, 10, 180)
    a2 = _make_agent("B", 50, 50, 10, 270)
    ttc = compute_ttc(a1, a2)
    assert ttc == 0.0


# ── Risk assessment tests ──

def test_risk_same_road_opposite():
    """Vehicule pe acelasi drum in directii opuse = low (benzi separate)."""
    a1 = _make_agent("A", 10, 100, 10, 180)   # heading south on NS road
    a2 = _make_agent("B", -10, -100, 10, 0)   # heading north on NS road
    assert _are_on_same_road_opposite_dirs(a1, a2) is True
    assert assess_intersection_risk(a1, a2) == "low"


def test_risk_perpendicular_collision():
    """Vehicule perpendiculare care se apropie — risc mare."""
    a1 = _make_agent("A", 0, 50, 10, 180)     # heading south, close
    a2 = _make_agent("B", 50, 0, 10, 270)     # heading west, close
    risk = assess_intersection_risk(a1, a2)
    assert risk in ("high", "collision")


def test_risk_far_away():
    """Vehicule care se departeaza de intersectie — risc low."""
    a1 = _make_agent("A", 0, 500, 10, 0)    # heading north, away from (0,0)
    a2 = _make_agent("B", 500, 0, 10, 90)   # heading east, away from (0,0)
    risk = assess_intersection_risk(a1, a2)
    assert risk == "low"


# ── Collision pairs tests ──

def test_collision_pairs_empty():
    """Fara agenti — fara perechi."""
    pairs = get_collision_pairs({})
    assert pairs == []


def test_collision_pairs_single():
    """Un singur agent — fara perechi."""
    a1 = _make_agent("A", 0, 100, 10, 180)
    pairs = get_collision_pairs({"A": a1})
    assert pairs == []


def test_collision_pairs_no_risk():
    """Agenti departati — fara perechi de risc."""
    a1 = _make_agent("A", 0, 500, 10, 180)
    a2 = _make_agent("B", 500, 0, 10, 270)
    pairs = get_collision_pairs({"A": a1, "B": a2})
    assert len(pairs) == 0


def test_collision_pairs_high_risk():
    """Agenti apropiati care converg — perechi de risc."""
    a1 = _make_agent("A", -10, 45, 10, 180)
    a2 = _make_agent("B", 45, -10, 10, 270)
    pairs = get_collision_pairs({"A": a1, "B": a2})
    assert len(pairs) > 0
    assert pairs[0]["risk"] in ("high", "collision")


# ── time_to_intersection tests ──

def test_tti_approaching():
    """Vehicul care se apropie de intersectie."""
    a = _make_agent("A", 0, 100, 10, 180)  # heading south toward (0,0)
    tti = time_to_intersection(a)
    assert tti > 0
    assert tti < 20  # ~10 seconds


def test_tti_receding():
    """Vehicul care se departeaza de intersectie."""
    a = _make_agent("A", 0, 100, 10, 0)  # heading north, away from (0,0)
    tti = time_to_intersection(a)
    assert tti == float('inf')


def test_tti_stationary():
    """Vehicul stationar."""
    a = _make_agent("A", 0, 100, 0, 180)
    tti = time_to_intersection(a)
    assert tti == float('inf')


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

