"""
v2x_channel.py — Canal de comunicare V2X shared intre toti agentii.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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


class V2XChannel:

    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Dict[str, V2XMessage] = {}
        self._history: List[V2XMessage] = []
        self._max_history = 500

    def publish(self, message: V2XMessage):
        with self._lock:
            self._messages[message.agent_id] = message
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history.pop(0)

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
        with self._lock:
            self._messages.pop(agent_id, None)

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
                }
                for m in recent
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
                }
                for agent_id, m in self._messages.items()
            }


channel = V2XChannel()