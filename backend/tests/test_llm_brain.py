"""
test_llm_brain.py — Teste unitare pentru AgentMemory si CircuitBreaker.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_brain import AgentMemory, CircuitBreaker


# ══════════════════════════════════════════════════════════════
#  AgentMemory tests
# ══════════════════════════════════════════════════════════════

class TestAgentMemory:

    def test_record_decision_populates_history(self):
        mem = AgentMemory("V1")
        mem.record_decision("test situation", {"action": "go", "speed": 10.0, "reason": "clear"})
        assert len(mem._decisions) == 1
        assert mem._last_action == "go"

    def test_multiple_decisions(self):
        mem = AgentMemory("V1")
        for i in range(5):
            mem.record_decision(f"step {i}", {"action": "go", "speed": 10.0, "reason": "clear"})
        assert len(mem._decisions) == 5

    def test_decision_maxlen_respected(self):
        mem = AgentMemory("V1", max_decisions=3)
        for i in range(10):
            mem.record_decision(f"step {i}", {"action": "go", "speed": 10.0, "reason": "clear"})
        assert len(mem._decisions) == 3

    def test_consecutive_same_action_counter(self):
        mem = AgentMemory("V1")
        for _ in range(5):
            mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        assert mem._consecutive_same_action == 4  # first one doesn't count as repeat
        assert mem._last_action == "stop"

    def test_consecutive_counter_resets_on_different_action(self):
        mem = AgentMemory("V1")
        for _ in range(5):
            mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        mem.record_decision("x", {"action": "go", "speed": 10.0, "reason": "green"})
        assert mem._consecutive_same_action == 0
        assert mem._last_action == "go"

    def test_action_counts(self):
        mem = AgentMemory("V1")
        mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        mem.record_decision("x", {"action": "yield", "speed": 2.0, "reason": "right_of_way"})
        mem.record_decision("x", {"action": "brake", "speed": 1.0, "reason": "ttc"})
        assert mem._total_stops == 2
        assert mem._total_yields == 1
        assert mem._total_brakes == 1

    def test_record_near_miss_adds_event(self):
        mem = AgentMemory("V1")
        mem.record_near_miss("V2", 2.5, "high")
        assert len(mem._near_misses) == 1
        assert mem._near_misses[0]["other_vehicle"] == "V2"
        assert mem._near_misses[0]["ttc"] == 2.5

    def test_near_miss_creates_lesson(self):
        mem = AgentMemory("V1")
        mem.record_near_miss("V2", 2.5, "high")
        assert len(mem._lessons) == 1
        assert "V2" in mem._lessons[0]

    def test_duplicate_lessons_not_added(self):
        mem = AgentMemory("V1")
        mem.record_near_miss("V2", 2.5, "high")
        mem.record_near_miss("V2", 2.5, "high")
        assert len(mem._lessons) == 1

    def test_record_v2x_alert(self):
        mem = AgentMemory("V1")
        mem.record_v2x_alert("V2", "emergency", "ambulance approaching")
        assert len(mem._v2x_alerts) == 1
        assert mem._v2x_alerts[0]["from"] == "V2"
        assert mem._v2x_alerts[0]["type"] == "emergency"

    def test_get_memory_context_empty(self):
        mem = AgentMemory("V1")
        ctx = mem.get_memory_context()
        assert ctx == ""

    def test_get_memory_context_with_data(self):
        mem = AgentMemory("V1")
        mem.record_decision("situation1", {"action": "go", "speed": 10.0, "reason": "clear"})
        mem.record_near_miss("V2", 2.0, "collision")
        ctx = mem.get_memory_context()
        assert "DECISION HISTORY" in ctx
        assert "NEAR-MISS" in ctx
        assert "LESSONS" in ctx

    def test_get_memory_context_with_v2x(self):
        mem = AgentMemory("V1")
        mem.record_v2x_alert("V2", "warning", "braking hard")
        ctx = mem.get_memory_context()
        assert "V2X ALERTS" in ctx

    def test_get_memory_context_with_stats_warning(self):
        mem = AgentMemory("V1")
        for _ in range(5):
            mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        ctx = mem.get_memory_context()
        assert "WARNING" in ctx
        assert "stop" in ctx

    def test_is_stuck_by_consecutive_actions(self):
        mem = AgentMemory("V1")
        for _ in range(20):
            mem.record_decision("waiting", {"action": "stop", "speed": 0.0, "reason": "red"})
        assert mem._consecutive_same_action >= 15
        # Need wait_start too
        mem._wait_start = time.time() - 15
        assert mem.is_stuck() is True

    def test_is_stuck_by_wait_time(self):
        mem = AgentMemory("V1")
        mem._wait_start = time.time() - 11.0  # waiting > 10s
        assert mem.is_stuck() is True

    def test_not_stuck_when_moving(self):
        mem = AgentMemory("V1")
        mem.record_decision("x", {"action": "go", "speed": 10.0, "reason": "clear"})
        assert mem.is_stuck() is False

    def test_get_stats(self):
        mem = AgentMemory("V1")
        mem.record_decision("x", {"action": "go", "speed": 10.0, "reason": "clear"})
        mem.record_near_miss("V2", 2.0, "high")
        stats = mem.get_stats()
        assert stats["memory_decisions"] == 1
        assert stats["near_misses"] == 1
        assert "is_stuck" in stats
        assert "time_waiting" in stats

    def test_reset(self):
        mem = AgentMemory("V1")
        mem.record_decision("x", {"action": "go", "speed": 5, "reason": "y"})
        mem.record_near_miss("V2", 2.0, "high")
        mem.record_v2x_alert("V3", "warning", "msg")
        mem.reset()
        assert len(mem._decisions) == 0
        assert len(mem._near_misses) == 0
        assert len(mem._v2x_alerts) == 0
        assert len(mem._lessons) == 0
        assert mem._total_stops == 0
        assert mem._last_action is None

    def test_waiting_time_tracking(self):
        mem = AgentMemory("V1")
        mem.record_decision("x", {"action": "stop", "speed": 0.0, "reason": "red"})
        assert mem._wait_start is not None
        # Now "resume"
        mem.record_decision("x", {"action": "go", "speed": 10.0, "reason": "green"})
        assert mem._wait_start is None
        assert mem._time_waiting >= 0


# ══════════════════════════════════════════════════════════════
#  CircuitBreaker tests
# ══════════════════════════════════════════════════════════════

class TestCircuitBreaker:

    def test_closed_by_default(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, window_seconds=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        cb.record_failure()
        assert cb.state != "closed"
        # After cooldown (0s), should transition to half_open
        time.sleep(0.01)
        assert cb.state == "half_open"
        assert cb.allow_request() is True

    def test_success_resets_to_closed(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        cb.record_failure()
        time.sleep(0.01)
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.5)
        cb.record_failure()
        # Should be OPEN now
        assert cb.allow_request() is False
        # Wait for cooldown to transition to HALF_OPEN
        time.sleep(0.6)
        assert cb.state == "half_open"
        cb.record_failure()
        # Should be OPEN again immediately after failed test call
        # Check _state directly since cooldown hasn't elapsed yet
        assert cb._state == "open"

    def test_get_stats(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "circuit_state" in stats
        assert "recent_failures" in stats
        assert "failure_threshold" in stats
        assert "total_successes" in stats
        assert "total_circuit_trips" in stats

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_success_increments_counter(self):
        cb = CircuitBreaker()
        cb.record_success()
        cb.record_success()
        stats = cb.get_stats()
        assert stats["total_successes"] == 2

    def test_trip_counter(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.5)
        cb.record_failure()  # trip 1
        time.sleep(0.6)      # wait for cooldown to enter half_open
        assert cb.state == "half_open"
        cb.record_failure()  # trip 2 (half_open -> open again)
        stats = cb.get_stats()
        assert stats["total_circuit_trips"] == 2

    def test_old_failures_evicted(self):
        cb = CircuitBreaker(failure_threshold=5, window_seconds=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)  # wait for window to expire
        cb.record_failure()  # this should evict old ones
        # Should still be closed since old failures expired
        assert cb.state == "closed"

