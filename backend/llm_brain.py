"""
llm_brain.py — Modul LLM care da fiecarui vehicul un "creier" AI cu MEMORIE PROPRIE.

Fiecare masina (agent) isi construieste un prompt cu situatia curenta,
istoricul deciziilor anterioare si alertele V2X primite,
si primeste de la LLM o decizie autonoma (action + recommended_speed + reason).
Foloseste Google Gemini (configurat prin .env).

Cerinte indeplinite:
- Memorie proprie per agent (istoric decizii, near-misses, lectii invatate)
- Perceptie prin mesaje V2X (alerte broadcast de la alti agenti)
- Decizii autonome non-deterministe (contextul memoriei + V2X variaza la fiecare pas)
"""

import os
import json
import time
import threading
import logging
from collections import deque
from typing import Dict, Optional, Any, List

logger = logging.getLogger("llm_brain")

# --- Config din .env ---
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_CALL_INTERVAL = float(os.getenv("LLM_CALL_INTERVAL", "0.6"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "4.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "300"))

# --- Google Gemini client (lazy init) ---
_client = None
_client_lock = threading.Lock()
_client_init_attempted = False


def _get_client():
    global _client, _client_init_attempted
    if _client is not None:
        return _client
    if _client_init_attempted:
        return None
    with _client_lock:
        if _client is not None:
            return _client
        if _client_init_attempted:
            return None
        _client_init_attempted = True
        if not GEMINI_API_KEY or "INLOCUIESTE" in GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — LLM disabled, using fallback.")
            return None
        try:
            from google import genai
            _client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info(f"Google Gemini client initialized (model={LLM_MODEL})")
            return _client
        except Exception as e:
            logger.error(f"Failed to init Gemini client: {e}")
            return None


# ──────────────────────── CIRCUIT BREAKER ────────────────────────

class CircuitBreaker:
    """
    Circuit breaker pentru apeluri LLM.

    Stari:
      CLOSED  — normal, apelurile trec
      OPEN    — LLM dezactivat automat dupa prea multe erori consecutive
      HALF_OPEN — dupa cooldown, se incearca un singur apel de test

    Daca rata de erori depaseste threshold-ul in fereastra de timp,
    circuit-ul se deschide si LLM-ul e dezactivat temporar.
    Dupa cooldown_seconds, se incearca un apel (half-open).
    Daca reuseste => CLOSED. Daca esueaza => OPEN din nou.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: float = 30.0,
        cooldown_seconds: float = 30.0,
    ):
        self._threshold = failure_threshold
        self._window = window_seconds
        self._cooldown = cooldown_seconds

        self._state = self.CLOSED
        self._failures: list = []       # timestamps of recent failures
        self._successes: int = 0
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0
        self._total_trips: int = 0      # how many times circuit opened
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                # Check if cooldown has elapsed => transition to HALF_OPEN
                if time.time() - self._opened_at >= self._cooldown:
                    self._state = self.HALF_OPEN
                    logger.info("[CircuitBreaker] HALF_OPEN — testing one LLM call")
            return self._state

    def allow_request(self) -> bool:
        """Returns True if the LLM call should proceed."""
        s = self.state  # triggers state transition check
        if s == self.CLOSED:
            return True
        if s == self.HALF_OPEN:
            return True  # allow exactly one test call
        return False  # OPEN — block

    def record_success(self):
        """Called after a successful LLM call."""
        with self._lock:
            self._successes += 1
            if self._state == self.HALF_OPEN:
                self._state = self.CLOSED
                self._failures.clear()
                logger.info("[CircuitBreaker] CLOSED — LLM recovered, resuming normal operation")

    def record_failure(self):
        """Called after a failed LLM call."""
        now = time.time()
        with self._lock:
            self._last_failure_time = now
            # Evict old failures outside the window
            self._failures = [t for t in self._failures if now - t < self._window]
            self._failures.append(now)

            if self._state == self.HALF_OPEN:
                # Test call failed — reopen
                self._state = self.OPEN
                self._opened_at = now
                self._total_trips += 1
                logger.warning("[CircuitBreaker] OPEN (again) — test call failed, LLM disabled")
            elif self._state == self.CLOSED:
                if len(self._failures) >= self._threshold:
                    self._state = self.OPEN
                    self._opened_at = now
                    self._total_trips += 1
                    logger.warning(
                        f"[CircuitBreaker] OPEN — {len(self._failures)} failures in "
                        f"{self._window}s, LLM disabled for {self._cooldown}s"
                    )

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "circuit_state": self._state,
                "recent_failures": len(self._failures),
                "failure_threshold": self._threshold,
                "total_successes": self._successes,
                "total_circuit_trips": self._total_trips,
                "cooldown_seconds": self._cooldown,
            }

    def reset(self):
        with self._lock:
            self._state = self.CLOSED
            self._failures.clear()
            self._successes = 0
            self._last_failure_time = 0.0
            self._opened_at = 0.0


# Global circuit breaker — shared across all vehicle brains
_circuit_breaker = CircuitBreaker(
    failure_threshold=5,   # 5 erori consecutive in fereastra
    window_seconds=30.0,   # fereastra de 30s
    cooldown_seconds=30.0, # asteapta 30s inainte de retry
)


def get_circuit_breaker_stats() -> dict:
    """Returneaza statisticile circuit breaker-ului (pentru monitoring)."""
    return _circuit_breaker.get_stats()


# ──────────────────────── AGENT MEMORY ────────────────────────

class AgentMemory:
    """
    Memorie proprie per vehicul. Stocheaza:
    - Istoricul deciziilor (ultimele N pasi)
    - Near-misses (situatii periculoase evitate)
    - Alerte V2X primite de la alti agenti
    - Lectii invatate (patterns observate)
    """

    def __init__(self, agent_id: str, max_decisions: int = 20, max_events: int = 10):
        self.agent_id = agent_id
        self._decisions: deque = deque(maxlen=max_decisions)
        self._near_misses: deque = deque(maxlen=max_events)
        self._v2x_alerts: deque = deque(maxlen=max_events)
        self._lessons: deque = deque(maxlen=5)
        self._total_stops = 0
        self._total_yields = 0
        self._total_brakes = 0
        self._consecutive_same_action = 0
        self._last_action = None
        self._time_waiting = 0.0
        self._wait_start: Optional[float] = None

    def record_decision(self, situation: str, decision: Dict[str, Any]):
        """Salveaza o decizie in memoria agentului."""
        entry = {
            "step": len(self._decisions),
            "time": time.time(),
            "situation": situation,
            "action": decision["action"],
            "speed": decision["speed"],
            "reason": decision["reason"],
        }
        self._decisions.append(entry)

        # Track consecutive same actions
        if decision["action"] == self._last_action:
            self._consecutive_same_action += 1
        else:
            self._consecutive_same_action = 0
        self._last_action = decision["action"]

        # Track action counts
        if decision["action"] == "stop":
            self._total_stops += 1
        elif decision["action"] == "yield":
            self._total_yields += 1
        elif decision["action"] == "brake":
            self._total_brakes += 1

        # Track waiting time
        if decision["action"] in ("stop", "yield") and decision["speed"] < 0.5:
            if self._wait_start is None:
                self._wait_start = time.time()
        else:
            if self._wait_start is not None:
                self._time_waiting += time.time() - self._wait_start
                self._wait_start = None

    def record_near_miss(self, other_id: str, ttc: float, risk: str):
        """Inregistreaza o situatie periculoasa evitata."""
        self._near_misses.append({
            "time": time.time(),
            "other_vehicle": other_id,
            "ttc": ttc,
            "risk_level": risk,
        })
        # Invata din near-miss
        lesson = f"Near-miss with {other_id} (TTC={ttc:.1f}s) — be more cautious approaching"
        if lesson not in list(self._lessons):
            self._lessons.append(lesson)

    def record_v2x_alert(self, from_id: str, alert_type: str, message: str):
        """Inregistreaza o alerta V2X primita de la alt agent."""
        self._v2x_alerts.append({
            "time": time.time(),
            "from": from_id,
            "type": alert_type,
            "message": message,
        })

    def get_memory_context(self) -> str:
        """Construieste un rezumat text al memoriei pentru includere in prompt."""
        parts = []

        # Istoricul deciziilor recente (ultimele 5)
        if self._decisions:
            parts.append("MY RECENT DECISION HISTORY:")
            recent = list(self._decisions)[-5:]
            for d in recent:
                parts.append(
                    f"  Step {d['step']}: {d['situation']} => "
                    f"{d['action']} (speed={d['speed']:.1f}, reason={d['reason']})"
                )

        # Behavioral stats
        stats_parts = []
        if self._total_stops > 0:
            stats_parts.append(f"total_stops={self._total_stops}")
        if self._total_yields > 0:
            stats_parts.append(f"total_yields={self._total_yields}")
        if self._time_waiting > 0:
            wait = self._time_waiting
            if self._wait_start:
                wait += time.time() - self._wait_start
            stats_parts.append(f"time_waiting={wait:.1f}s")
        if self._consecutive_same_action > 3:
            stats_parts.append(
                f"WARNING: same action '{self._last_action}' repeated {self._consecutive_same_action} times"
            )
        if stats_parts:
            parts.append(f"MY BEHAVIOR STATS: {', '.join(stats_parts)}")

        # Near-misses
        if self._near_misses:
            parts.append("NEAR-MISS EVENTS I REMEMBER:")
            for nm in list(self._near_misses)[-3:]:
                parts.append(
                    f"  - Close call with {nm['other_vehicle']} "
                    f"(TTC={nm['ttc']:.1f}s, risk={nm['risk_level']})"
                )

        # V2X alerts
        recent_alerts = [a for a in self._v2x_alerts if time.time() - a["time"] < 5.0]
        if recent_alerts:
            parts.append("V2X ALERTS RECEIVED:")
            for a in recent_alerts[-3:]:
                parts.append(f"  - From {a['from']}: [{a['type']}] {a['message']}")

        # Lessons learned
        if self._lessons:
            parts.append("LESSONS I LEARNED:")
            for lesson in self._lessons:
                parts.append(f"  - {lesson}")

        return "\n".join(parts) if parts else ""

    def is_stuck(self) -> bool:
        """Detecteaza daca agentul e blocat (asteapta prea mult)."""
        if self._wait_start and (time.time() - self._wait_start) > 10.0:
            return True
        if self._consecutive_same_action > 15 and self._last_action in ("stop", "yield"):
            return True
        return False

    def get_stats(self) -> dict:
        """Returneaza statistici pentru debug/frontend."""
        wait = self._time_waiting
        if self._wait_start:
            wait += time.time() - self._wait_start
        return {
            "memory_decisions": len(self._decisions),
            "near_misses": len(self._near_misses),
            "v2x_alerts_received": len(self._v2x_alerts),
            "lessons_learned": len(self._lessons),
            "total_stops": self._total_stops,
            "total_yields": self._total_yields,
            "total_brakes": self._total_brakes,
            "time_waiting": round(wait, 1),
            "is_stuck": self.is_stuck(),
        }

    def reset(self):
        """Reseteaza memoria (la restart simulare)."""
        self._decisions.clear()
        self._near_misses.clear()
        self._v2x_alerts.clear()
        self._lessons.clear()
        self._total_stops = 0
        self._total_yields = 0
        self._total_brakes = 0
        self._consecutive_same_action = 0
        self._last_action = None
        self._time_waiting = 0.0
        self._wait_start = None


# ──────────────────────── SYSTEM PROMPT ────────────────────────

SYSTEM_PROMPT = """You are an autonomous AI driving agent controlling a single vehicle in a V2X (Vehicle-to-Everything) intersection simulation.

You have your OWN MEMORY of past decisions and experiences. Use this memory to make BETTER decisions over time. Do NOT repeat the same mistakes.

COORDINATE SYSTEM:
- The intersection center is at (0, 0).
- Positive Y = North, Negative Y = South.
- Positive X = East, Negative X = West.
- Direction 0° = heading North (increasing Y), 90° = East, 180° = South, 270° = West.

ROAD RULES (European):
- Vehicles drive on the RIGHT side of the road.
- At intersections WITHOUT traffic lights: yield to vehicles coming from your RIGHT (priority de dreapta).
- At intersections WITH traffic lights: obey the signal. RED = STOP before the stop line (distance ~35 units from center). GREEN = proceed.
- Emergency vehicles (ambulances) always have priority. If you detect one nearby, yield immediately.
- If you have already entered the intersection (distance < 35 from center), CONTINUE through — do NOT stop inside.
- When stopped at red, resume immediately when light turns green.

STOP LINE:
- The stop line is at distance 35 from center on your movement axis.
- If your signal is RED and you haven't entered the intersection yet, you must decelerate and stop before the stop line.
- Calculate braking: if distance to stop line < 20, set speed proportionally. If < 1, speed = 0.

COLLISION AVOIDANCE:
- Always check Time-To-Collision (TTC) with nearby vehicles.
- If TTC < 3 seconds with any vehicle, take evasive action (brake hard).
- If TTC < 6 seconds, reduce speed significantly.

MEMORY & ADAPTATION:
- You have access to your recent decision history. Use it to maintain consistency and adapt.
- If a previous decision led to a risky situation (near-miss), be MORE cautious in similar scenarios.
- Avoid oscillating between contradictory decisions (e.g., go/stop/go/stop).
- If you have been stopped/yielding for a long time and the path is now clear, PROCEED — do not stay stuck forever.
- Pay attention to V2X alerts from other vehicles — they share their intentions and warnings.
- If you notice you keep repeating the same action without progress, consider changing strategy.

You MUST respond ONLY with a valid JSON object (no markdown, no explanation):
{
  "action": "go" | "yield" | "brake" | "stop",
  "speed": <float 0.0 to 25.0>,
  "reason": "<short reason string, max 30 chars>"
}
"""


# ──────────────────────── PROMPT BUILDER ────────────────────────

def build_situation_prompt(
    agent_id: str,
    x: float, y: float,
    speed: float,
    direction: float,
    intention: str,
    is_emergency: bool,
    entered_intersection: bool,
    traffic_light: Optional[str],
    others: list,
    risk_level: str,
    distance_to_stop_line: float,
    memory_context: str = "",
    v2x_broadcasts: str = "",
) -> str:
    """Construieste promptul cu situatia curenta + memorie + V2X."""

    parts = []
    parts.append(f"I am vehicle {agent_id}.")
    parts.append(f"Position: ({x:.1f}, {y:.1f}), Speed: {speed:.1f} m/s ({speed*3.6:.0f} km/h), Heading: {direction}°.")
    parts.append(f"Intention: {intention}. Emergency: {is_emergency}.")
    parts.append(f"Inside intersection: {entered_intersection}. Distance to stop line: {distance_to_stop_line:.1f} units.")
    parts.append(f"Current risk assessment: {risk_level}.")

    if traffic_light is not None:
        parts.append(f"Traffic light for my axis: {traffic_light.upper()}.")
    else:
        parts.append("No traffic light — use right-of-way rules.")

    if others:
        parts.append(f"\nNEARBY VEHICLES ({len(others)}):")
        for o in others:
            parts.append(
                f"  - {o['id']}: pos=({o['x']:.1f},{o['y']:.1f}), speed={o['speed']:.1f} m/s, "
                f"heading={o['direction']}°, intention={o['intention']}, "
                f"emergency={o.get('is_emergency', False)}, "
                f"distance_to_me={o.get('dist', 0):.1f}, "
                f"ttc={o.get('ttc', 'inf')}, "
                f"their_decision={o.get('decision', 'unknown')}"
            )
    else:
        parts.append("\nNo other vehicles detected nearby.")

    # V2X broadcast messages from other vehicles
    if v2x_broadcasts:
        parts.append(f"\n{v2x_broadcasts}")

    # Memory context (past decisions, near-misses, lessons)
    if memory_context:
        parts.append(f"\n{memory_context}")

    parts.append("\nBased on my current situation, my memory of past experiences, and V2X messages, what should I do? Respond with JSON only.")
    return "\n".join(parts)


# ──────────────────────── LLM BRAIN ────────────────────────

class LLMBrain:
    """
    Per-vehicle LLM brain cu MEMORIE PROPRIE.
    Gestioneaza rate-limiting, memorie, perceptie V2X si fallback.
    Foloseste Google Gemini API.
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._last_call_time = 0.0
        self._last_decision: Optional[Dict[str, Any]] = None
        self._call_count = 0
        self._error_count = 0

        # Memorie proprie per agent
        self.memory = AgentMemory(agent_id)

    def decide(
        self,
        x: float, y: float,
        speed: float,
        direction: float,
        intention: str,
        is_emergency: bool,
        entered_intersection: bool,
        traffic_light: Optional[str],
        others: list,
        risk_level: str,
        distance_to_stop_line: float,
        v2x_broadcasts: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Apeleaza LLM-ul si returneaza decizia.
        Include memoria agentului si alertele V2X in prompt.
        Returneaza None daca LLM nu e disponibil (se va folosi fallback-ul deterministic).
        """
        if not LLM_ENABLED:
            return None

        # Circuit breaker — daca LLM-ul a picat prea des, skip automat
        if not _circuit_breaker.allow_request():
            return self._last_decision

        # Rate limiting
        now = time.time()
        if now - self._last_call_time < LLM_CALL_INTERVAL:
            return self._last_decision

        client = _get_client()
        if client is None:
            return None

        self._last_call_time = now

        # Construieste un summary al situatiei curente (pentru memorare)
        situation_summary = (
            f"pos=({x:.0f},{y:.0f}) spd={speed:.1f} risk={risk_level} "
            f"light={traffic_light or 'none'} near={len(others)} "
            f"dist_stop={distance_to_stop_line:.0f} inside={entered_intersection}"
        )

        # Obtine contextul memoriei
        memory_context = self.memory.get_memory_context()

        # Inregistreaza near-misses din datele curente
        for o in others:
            ttc_str = o.get("ttc", "inf")
            try:
                ttc_val = float(ttc_str.replace("s", "")) if isinstance(ttc_str, str) else float(ttc_str)
            except (ValueError, AttributeError):
                ttc_val = float("inf")
            if ttc_val < 4.0:
                self.memory.record_near_miss(o["id"], ttc_val, risk_level)

        prompt = build_situation_prompt(
            agent_id=self.agent_id,
            x=x, y=y, speed=speed,
            direction=direction,
            intention=intention,
            is_emergency=is_emergency,
            entered_intersection=entered_intersection,
            traffic_light=traffic_light,
            others=others,
            risk_level=risk_level,
            distance_to_stop_line=distance_to_stop_line,
            memory_context=memory_context,
            v2x_broadcasts=v2x_broadcasts,
        )

        try:
            from google.genai import types

            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=LLM_MAX_TOKENS,
                    temperature=0.15,
                ),
            )

            text = response.text.strip()
            # Parse JSON — handle markdown wrapping
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            decision = json.loads(text)

            # Validate
            action = decision.get("action", "go")
            if action not in ("go", "yield", "brake", "stop"):
                action = "go"

            spd = float(decision.get("speed", speed))
            spd = max(0.0, min(25.0, spd))

            reason = str(decision.get("reason", "llm_decision"))[:50]

            result = {
                "action": action,
                "speed": spd,
                "reason": reason,
            }
            self._last_decision = result
            self._call_count += 1
            _circuit_breaker.record_success()

            # Salveaza decizia in memorie
            self.memory.record_decision(situation_summary, result)

            logger.debug(f"[{self.agent_id}] LLM: {result}")
            return result

        except json.JSONDecodeError as e:
            self._error_count += 1
            _circuit_breaker.record_failure()
            logger.warning(f"[{self.agent_id}] LLM JSON parse error: {e}")
            return self._last_decision
        except Exception as e:
            self._error_count += 1
            _circuit_breaker.record_failure()
            logger.warning(f"[{self.agent_id}] LLM call failed: {e}")
            return self._last_decision

    def get_stats(self) -> dict:
        memory_stats = self.memory.get_stats()
        cb_stats = _circuit_breaker.get_stats()
        return {
            "llm_calls": self._call_count,
            "llm_errors": self._error_count,
            "last_decision": self._last_decision,
            "circuit_breaker": cb_stats["circuit_state"],
            **memory_stats,
        }

    def reset(self):
        """Reseteaza brain-ul la restart simulare."""
        self._last_call_time = 0.0
        self._last_decision = None
        self._call_count = 0
        self._error_count = 0
        self.memory.reset()

