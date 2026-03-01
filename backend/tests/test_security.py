
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


def test_hmac_sign_verify():
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, time.time())
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_hmac_verify_valid():
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    assert verify_signature("VH_A", 10.0, 20.0, 5.0, 180.0, ts, sig) is True


def test_hmac_verify_tampered():
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    assert verify_signature("VH_A", 99.0, 20.0, 5.0, 180.0, ts, sig) is False


def test_hmac_verify_wrong_agent():
    ts = time.time()
    sig = sign_message("VH_A", 10.0, 20.0, 5.0, 180.0, ts)
    assert verify_signature("VH_B", 10.0, 20.0, 5.0, 180.0, ts, sig) is False


def test_validate_agent_id_valid():
    assert validate_agent_id("VH_A") == "VH_A"
    assert validate_agent_id("AMBULANCE") == "AMBULANCE"
    assert validate_agent_id("BG_001") == "BG_001"


def test_validate_agent_id_invalid():
    assert validate_agent_id("") is None
    assert validate_agent_id(None) is None
    assert validate_agent_id(123) is None
    assert validate_agent_id("a" * 50) is None
    assert validate_agent_id("VH-A") is None
    assert validate_agent_id("VH A") is None


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
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=float('nan'), y=20.0, speed=5.0,
        direction=180.0, intention="straight",
        risk_level="low", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert len(errors) > 0
    assert sanitized["x"] == -500.0


def test_validate_message_inf():
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=10.0, y=20.0, speed=float('inf'),
        direction=180.0, intention="straight",
        risk_level="low", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert sanitized["speed"] == 0.0


def test_validate_message_bad_risk():
    valid, sanitized, errors = validate_message(
        agent_id="VH_A", agent_type="vehicle",
        x=10.0, y=20.0, speed=5.0,
        direction=180.0, intention="straight",
        risk_level="INVALID", decision="go",
        timestamp=time.time(), is_emergency=False,
    )
    assert valid is False
    assert sanitized["risk_level"] == "low"


def test_stale_detector_fresh():
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    assert "VH_A" not in d.stale_agents()


def test_stale_detector_timeout():
    d = StaleAgentDetector(timeout=0.1)
    d.touch("VH_A")
    time.sleep(0.15)
    assert "VH_A" in d.stale_agents()


def test_stale_detector_remove():
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    d.remove("VH_A")
    assert "VH_A" not in d.stale_agents()


def test_stale_detector_reset():
    d = StaleAgentDetector(timeout=1.0)
    d.touch("VH_A")
    d.touch("VH_B")
    d.reset()
    assert d.stale_agents() == []


def test_rate_limiter_allows():
    rl = RateLimiter(max_per_sec=5)
    for _ in range(5):
        assert rl.allow("VH_A") is True


def test_rate_limiter_blocks():
    rl = RateLimiter(max_per_sec=2)
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_A") is False


def test_rate_limiter_per_agent():
    rl = RateLimiter(max_per_sec=1)
    assert rl.allow("VH_A") is True
    assert rl.allow("VH_B") is True
    assert rl.allow("VH_A") is False
    assert rl.allow("VH_B") is False


def test_rate_limiter_reset():
    rl = RateLimiter(max_per_sec=1)
    rl.allow("VH_A")
    rl.allow("VH_A")
    rl.reset()
    assert rl.allow("VH_A") is True


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
    raw = {
        "agent_id": "VH_A", "agent_type": "vehicle",
        "x": 9999.0, "y": -9999.0, "speed": 100.0,
        "direction": 180.0, "intention": "straight",
        "risk_level": "low", "decision": "go",
        "is_emergency": False, "timestamp": time.time(),
    }
    clean = sanitize_agent(raw)
    assert clean["x"] == 500.0
    assert clean["y"] == -500.0
    assert clean["speed"] == 50.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
