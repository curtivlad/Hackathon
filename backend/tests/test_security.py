"""
test_security.py — Teste unitare pentru modulul de securitate V2X.
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v2x_security import (
    sign_message, verify_signature,
    validate_agent_id, validate_message,
    StaleAgentDetector, RateLimiter,
    sanitize_agent,
    VALID_ACTIONS, VALID_RISKS,
)


# ── HMAC tests ──

def test_hmac_sign_verify():
    """Semnatura HMAC trebuie sa fie verificabila."""
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, time.time())
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex = 64 chars


def test_hmac_verify_valid():
    """Verificare cu aceeasi parametri — pass."""
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    assert verify_signature("VH_A", 10.0, 20.0, 5.0, 180.0, ts, sig) is True


def test_hmac_verify_tampered():
    """Verificare cu date modificate — fail."""
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    # Modificam x-ul
    assert verify_signature("VH_A", 99.0, 20.0, 5.0, 180.0, ts, sig) is False


def test_hmac_verify_wrong_agent():
    """Verificare cu alt agent_id — fail."""
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    assert verify_signature("VH_B", 10.0, 20.0, 5.0, 180.0, ts, sig) is False


# ── Validate agent_id tests ──

def test_validate_agent_id_valid():
    assert validate_agent_id("VH_A") == "VH_A"
    assert validate_agent_id("AMBULANCE") == "AMBULANCE"
    assert validate_agent_id("BG_001") == "BG_001"


def test_validate_agent_id_invalid():
    assert validate_agent_id("") is None
    assert validate_agent_id(None) is None
    assert validate_agent_id(123) is None
    assert validate_agent_id("a" * 50) is None  # too long
    assert validate_agent_id("VH-A") is None    # hyphen not allowed
    assert validate_agent_id("VH A") is None    # space not allowed


# ── Validate message tests ──

def test_validate_message_valid():
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=10.0, y=20.0, speed=5.0,
        direction=180.0, intention="straight",
        risk_level="low", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is True
    assert len(errors) == 0
    assert sanitized["agent_id"] == "VH_A"


def test_validate_message_nan():
    """NaN in coordonate — trebuie sanitizat."""
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=float('nan'), y=20.0, speed=5.0,
        direction=180.0, intention="straight",
        risk_level="low", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert len(errors) > 0
    # Sanitized x should be clamped, not NaN
    assert sanitized["x"] == -500.0  # _clamp returns lo for NaN


def test_validate_message_inf():
    """Inf in viteza — trebuie sanitizat."""
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=10.0, y=20.0, speed=float('inf'),
        direction=180.0, intention="straight",
        risk_level="low", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert sanitized["speed"] == 0.0  # _clamp returns lo for Inf


def test_validate_message_bad_risk():
    """Risk level invalid — sanitizat la 'low'."""
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=10.0, y=20.0, speed=5.0,
        direction=180.0, intention="straight",
        risk_level="INVALID", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert sanitized["risk_level"] == "low"


# ── Stale Agent Detector tests ──

def test_stale_detector_fresh():
    """Agent proaspat nu e stale."""
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    assert "VH_A" not in d.stale_agents()


def test_stale_detector_timeout():
    """Agent care nu a mai trimis — devine stale."""
    d = StaleAgentDetector(timeout=0.1)
    d.touch("VH_A")
    time.sleep(0.15)
    assert "VH_A" in d.stale_agents()


def test_stale_detector_remove():
    """Agent sters dispare din tracking."""
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    d.remove("VH_A")
    assert "VH_A" not in d.stale_agents()


def test_stale_detector_reset():
    """Reset curata totul."""
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    d.touch("VH_B")
    d.reset()
    assert d.stale_agents() == []


# ── Rate Limiter tests ──

def test_rate_limiter_allows():
    """Sub limita — permite."""
    rl = RateLimiter(max_per_sec=5)
    for _ in range(5):
        assert rl.allow("VH_A") is True


def test_rate_limiter_blocks():
    """Peste limita — blocheaza."""
    rl = RateLimiter(max_per_sec=2)
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_A") is False


def test_rate_limiter_per_agent():
    """Rate limit e per agent, nu global."""
    rl = RateLimiter(max_per_sec=1)
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_B") is True
    assert rl.allow("VH_A") is False
    assert rl.allow("VH_B") is False


def test_rate_limiter_reset():
    """Reset curata buckets."""
    rl = RateLimiter(max_per_sec=1)
    rl.allow("VH_A")
    rl.allow("VH_A")
    rl.reset()
    assert rl.allow("VH_A") is True


# ── Sanitize agent tests ──

def test_sanitize_agent_valid():
    raw = {
        "agent_id": "VH_A", "agent_type": "vehicle",
        "x": 10.0, "y": 20.0, "speed": 5.0,
        "direction": 180.0, "intention": "straight",
        "risk_level": "low", "decision": "go",
        "is_emergency": False, "timestamp": time.time(),
    }
    clean = sanitize_agent(raw)
    assert clean["agent_id"] == "VH_A"
    assert clean["x"] == 10.0
    assert clean["speed"] == 5.0


def test_sanitize_agent_clamps():
    """Valori in afara range-ului sunt clamped."""
    raw = {
        "agent_id": "VH_A", "agent_type": "vehicle",
        "x": 9999.0, "y": -9999.0, "speed": 100.0,
        "direction": 180.0, "intention": "straight",
        "risk_level": "low", "decision": "go",
        "is_emergency": False, "timestamp": time.time(),
    }
    clean = sanitize_agent(raw)
    assert clean["x"] == 500.0   # clamped to COORD_MAX
    assert clean["y"] == -500.0  # clamped to COORD_MIN
    assert clean["speed"] == 50.0  # clamped to SPEED_MAX


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

