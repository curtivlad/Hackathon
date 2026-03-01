
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger("v2x_channel")


@dataclass
class V2XMessage:
    agent_id: str
    agent_type: str
    x: float
    y: float
    speed: float
    direction: float
    intention: str
    risk_level: str
    decision: str
    timestamp: float = field(default_factory=time.time)
    is_emergency: bool = False
    is_police: bool = False
    is_drunk: bool = False
    pulling_over: bool = False
    arrested: bool = False
    hmac_signature: str = ""


@dataclass
class V2XBroadcast:
    from_id: str
    alert_type: str
    message: str
    timestamp: float = field(default_factory=time.time)
    target_id: Optional[str] = None


class V2XChannel:

    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Dict[str, V2XMessage] = {}
        self._history: List[V2XMessage] = []
        self._max_history = 500
        self._broadcasts: deque = deque(maxlen=200)
        self._rejected_messages = 0
        self._rejected_broadcasts = 0

    def publish(self, message: V2XMessage):
        from v2x_security import (sign_message, validate_message,
                                   stale_detector)

        valid, sanitized, errors = validate_message(
            message.agent_id, message.agent_type,
            message.x, message.y, message.speed,
            message.direction, message.intention,
            message.risk_level, message.decision,
            message.timestamp, message.is_emergency,
            message.is_drunk,
        )
        if not valid:
            self._rejected_messages += 1
            logger.warning(
                f"[SECURITY] Mesaj CORUPT de la {message.agent_id}: {errors}  "
                f"— aplicam datele sanitizate"
            )
            message.x = sanitized["x"]
            message.y = sanitized["y"]
            message.speed = sanitized["speed"]
            message.direction = sanitized["direction"]
            message.risk_level = sanitized["risk_level"]
            message.timestamp = sanitized["timestamp"]

        message.hmac_signature = sign_message(
            message.agent_id, message.x, message.y,
            message.speed, message.direction, message.timestamp,
        )

        stale_detector.touch(message.agent_id)

        with self._lock:
            self._messages[message.agent_id] = message
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def broadcast(self, alert: V2XBroadcast):
        from v2x_security import broadcast_limiter

        if not broadcast_limiter.allow(alert.from_id):
            self._rejected_broadcasts += 1
            return

        with self._lock:
            self._broadcasts.append(alert)

    def get_broadcasts_for(self, agent_id: str, last_seconds: float = 5.0) -> List[V2XBroadcast]:
        cutoff = time.time() - last_seconds
        with self._lock:
            return [
                b for b in self._broadcasts
                if b.timestamp >= cutoff
                and b.from_id != agent_id
                and (b.target_id is None or b.target_id == agent_id)
            ]

    def get_all_states(self) -> Dict[str, V2XMessage]:
        with self._lock:
            return dict(self._messages)

    def get_agent_state(self, agent_id: str) -> Optional[V2XMessage]:
        with self._lock:
            return self._messages.get(agent_id)

    def get_other_agents(self, my_id: str) -> Dict[str, V2XMessage]:
        with self._lock:
            return {k: v for k, v in self._messages.items() if k != my_id}

    def remove_agent(self, agent_id: str):
        from v2x_security import stale_detector
        with self._lock:
            self._messages.pop(agent_id, None)
        stale_detector.remove(agent_id)

    def cleanup_stale_agents(self) -> list:
        from v2x_security import stale_detector
        stale = stale_detector.stale_agents()
        removed = []
        for aid in stale:
            with self._lock:
                if aid in self._messages:
                    self._messages.pop(aid)
                    removed.append(aid)
            stale_detector.remove(aid)
        if removed:
            logger.warning(f"[SECURITY] Agenti INACTIVI stersi: {removed}")
        return removed

    def verify_message(self, agent_id: str) -> bool:
        from v2x_security import verify_signature
        with self._lock:
            msg = self._messages.get(agent_id)
            if msg is None:
                return False
        return verify_signature(
            msg.agent_id, msg.x, msg.y,
            msg.speed, msg.direction,
            msg.timestamp, msg.hmac_signature,
        )

    def get_history(self, last_n: int = 50) -> List[dict]:
        with self._lock:
            recent = self._history[-last_n:]
            return [
                {
                    "agent_id": m.agent_id,
                    "agent_type": m.agent_type,
                    "x": m.x,
                    "y": m.y,
                    "speed": m.speed,
                    "direction": m.direction,
                    "intention": m.intention,
                    "risk_level": m.risk_level,
                    "decision": m.decision,
                    "timestamp": m.timestamp,
                    "is_emergency": m.is_emergency,
                    "is_police": m.is_police,
                    "is_drunk": m.is_drunk,
                    "pulling_over": m.pulling_over,
                    "arrested": m.arrested,
                }
            ]

    def to_dict(self) -> dict:
        with self._lock:
            return {
                agent_id: {
                    "agent_id": m.agent_id,
                    "agent_type": m.agent_type,
                    "x": m.x,
                    "y": m.y,
                    "speed": m.speed,
                    "direction": m.direction,
                    "intention": m.intention,
                    "risk_level": m.risk_level,
                    "decision": m.decision,
                    "timestamp": m.timestamp,
                    "is_emergency": m.is_emergency,
                    "is_police": m.is_police,
                    "is_drunk": m.is_drunk,
                    "pulling_over": m.pulling_over,
                    "arrested": m.arrested,
                }
                for agent_id, m in self._messages.items()
            }

    def get_security_stats(self) -> dict:
        from v2x_security import stale_detector
        return {
            "rejected_messages": self._rejected_messages,
            "rejected_broadcasts": self._rejected_broadcasts,
            "stale_agents": stale_detector.stale_agents(),
            "active_agents": list(self._messages.keys()),
        }

    def clear_all(self):
        from v2x_security import stale_detector, broadcast_limiter
        with self._lock:
            self._messages.clear()
            self._history.clear()
            self._broadcasts.clear()
        self._rejected_messages = 0
        self._rejected_broadcasts = 0
        stale_detector.reset()
        broadcast_limiter.reset()


channel = V2XChannel()
