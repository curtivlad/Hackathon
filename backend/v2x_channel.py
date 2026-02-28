"""
v2x_channel.py
Canalul de comunicare shared intre toti agentii (vehicule + infrastructura).
Fiecare agent isi publica starea aici si citeste starea celorlalti.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class V2XMessage:
    """Un mesaj V2X trimis de un agent."""
    agent_id: str
    agent_type: str          # "vehicle" sau "infrastructure"
    x: float                 # pozitie pe axa X (metri)
    y: float                 # pozitie pe axa Y (metri)
    speed: float             # viteza curenta (m/s)
    direction: float         # unghi in grade (0=Nord, 90=Est, 180=Sud, 270=Vest)
    intention: str           # "straight", "turn_left", "turn_right", "stop"
    risk_level: str          # "low", "medium", "high", "collision"
    decision: str            # decizia luata: "go", "brake", "yield", "stop"
    timestamp: float = field(default_factory=time.time)
    is_emergency: bool = False


class V2XChannel:
    """
    Canal de comunicare shared intre agenti.
    Thread-safe: mai multi agenti pot scrie/citi simultan.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Dict[str, V2XMessage] = {}   # agent_id -> ultimul mesaj
        self._history: List[V2XMessage] = []          # toate mesajele (pentru log)
        self._max_history = 500

    def publish(self, message: V2XMessage):
        """Un agent isi publica starea pe canal."""
        with self._lock:
            self._messages[message.agent_id] = message
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def get_all_states(self) -> Dict[str, V2XMessage]:
        """Returneaza starea tuturor agentilor activi."""
        with self._lock:
            return dict(self._messages)

    def get_agent_state(self, agent_id: str) -> Optional[V2XMessage]:
        """Returneaza starea unui agent specific."""
        with self._lock:
            return self._messages.get(agent_id)

    def get_other_agents(self, my_id: str) -> Dict[str, V2XMessage]:
        """Returneaza starea tuturor agentilor, EXCEPTAND pe cel care intreaba."""
        with self._lock:
            return {k: v for k, v in self._messages.items() if k != my_id}

    def remove_agent(self, agent_id: str):
        """Sterge un agent de pe canal (a parasit intersectia)."""
        with self._lock:
            self._messages.pop(agent_id, None)

    def get_history(self, last_n: int = 50) -> List[dict]:
        """Returneaza ultimele N mesaje din istoric (pentru frontend)."""
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
        """Serializeaza tot canalul pentru a fi trimis prin WebSocket."""
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


# Instanta globala — importata de toti agentii
channel = V2XChannel()