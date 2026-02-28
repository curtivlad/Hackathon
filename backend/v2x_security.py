"""
v2x_security.py — Modul de securitate V2X.

Cerinta: Sistemul nu transmite date de localizare sau telemetrie fara protectie
si integreaza mecanisme de siguranta pentru situatii limita (agenti inactivi, date corupte).

Implementeaza:
1. Semnare HMAC-SHA256 a mesajelor V2X (integritate + autenticitate)
2. Validare date (range checks, NaN/Inf, tipuri corecte)
3. Detectie agenti inactivi (stale timeout + cleanup)
4. Rate limiting pe broadcast (anti-flood)
5. Sanitizare output catre frontend (nu se trimit date brute)
"""

import os
import hmac
import hashlib
import time
import math
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger("v2x_security")

# ─── CONFIG (din .env) ──────────────────────────────────────────────────────

V2X_HMAC_KEY = os.getenv("V2X_HMAC_KEY", "v2x-hmac-secret-change-in-prod")
_HMAC_KEY_BYTES = V2X_HMAC_KEY.encode("utf-8")

AGENT_STALE_TIMEOUT = float(os.getenv("AGENT_STALE_TIMEOUT", "5.0"))
BROADCAST_RATE_LIMIT = int(os.getenv("BROADCAST_RATE_LIMIT", "10"))  # per agent per sec
MAX_WS_CONNECTIONS = int(os.getenv("MAX_WS_CONNECTIONS", "20"))

# Limite fizice
COORD_MIN, COORD_MAX = -500.0, 500.0
SPEED_MIN, SPEED_MAX = 0.0, 50.0
MAX_STR_LEN = 64
MAX_ID_LEN = 32

VALID_ACTIONS = frozenset({"go", "yield", "brake", "stop"})
VALID_RISKS = frozenset({"low", "medium", "high", "collision"})
VALID_AGENT_TYPES = frozenset({"vehicle", "infrastructure"})


# ═══════════════════════════════════════════════════════════════════════════
#  1. HMAC  — semnare si verificare mesaje V2X
# ═══════════════════════════════════════════════════════════════════════════

def sign_message(agent_id: str, x: float, y: float,
                 speed: float, direction: float, timestamp: float) -> str:
    """Genereaza HMAC-SHA256 pentru un mesaj V2X."""
    payload = f"{agent_id}|{x:.4f}|{y:.4f}|{speed:.4f}|{direction:.4f}|{timestamp:.6f}"
    return hmac.new(_HMAC_KEY_BYTES, payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(agent_id: str, x: float, y: float,
                     speed: float, direction: float,
                     timestamp: float, signature: str) -> bool:
    """Verifica HMAC. Returneaza False daca semnatura e invalida."""
    expected = sign_message(agent_id, x, y, speed, direction, timestamp)
    return hmac.compare_digest(expected, signature)


# ═══════════════════════════════════════════════════════════════════════════
#  2. VALIDARE DATE  — range checks, NaN, tipuri
# ═══════════════════════════════════════════════════════════════════════════

def _finite(v: float) -> bool:
    return isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v))


def _clamp(v: float, lo: float, hi: float) -> float:
    if not _finite(v):
        return lo
    return max(lo, min(hi, v))


def validate_agent_id(aid: Any) -> Optional[str]:
    """Returneaza id-ul curatat sau None daca e invalid."""
    if not isinstance(aid, str):
        return None
    aid = aid.strip()
    if not aid or len(aid) > MAX_ID_LEN:
        return None
    if not all(c.isalnum() or c == '_' for c in aid):
        return None
    return aid


def validate_message(agent_id: str, agent_type: str,
                     x: float, y: float, speed: float,
                     direction: float, intention: str,
                     risk_level: str, decision: str,
                     timestamp: float,
                     is_emergency: bool,
                     is_drunk: bool = False) -> Tuple[bool, dict, list]:
    """
    Valideaza + sanitizeaza un mesaj V2X.
    Returneaza (valid, sanitized_dict, errors_list).
    """
    errors: list = []
    s: dict = {}

    # agent_id
    cid = validate_agent_id(agent_id)
    if cid is None:
        errors.append(f"bad agent_id: {agent_id!r}")
    s["agent_id"] = cid or "UNKNOWN"

    # agent_type
    if agent_type not in VALID_AGENT_TYPES:
        errors.append(f"bad agent_type: {agent_type!r}")
    s["agent_type"] = agent_type if agent_type in VALID_AGENT_TYPES else "vehicle"

    # coordonate
    for name, val in [("x", x), ("y", y)]:
        if not _finite(val):
            errors.append(f"{name} not finite: {val}")
        s[name] = round(_clamp(val, COORD_MIN, COORD_MAX), 4)

    # viteza
    if not _finite(speed):
        errors.append(f"speed not finite: {speed}")
    s["speed"] = round(_clamp(speed, SPEED_MIN, SPEED_MAX), 4)

    # directie
    if not _finite(direction):
        errors.append(f"direction not finite: {direction}")
        s["direction"] = 0.0
    else:
        s["direction"] = round(direction % 360.0, 4)

    # string-uri
    if not isinstance(intention, str) or len(intention) > MAX_STR_LEN:
        errors.append(f"bad intention: {intention!r}")
        s["intention"] = "straight"
    else:
        s["intention"] = intention

    if risk_level not in VALID_RISKS:
        errors.append(f"bad risk_level: {risk_level!r}")
    s["risk_level"] = risk_level if risk_level in VALID_RISKS else "low"

    # decision — poate fi si actiune infra (NS_GREEN etc.)
    if not isinstance(decision, str) or len(decision) > MAX_STR_LEN:
        errors.append(f"bad decision: {decision!r}")
        s["decision"] = "stop"
    else:
        s["decision"] = decision

    # timestamp — anti-replay (max 10s decalaj)
    now = time.time()
    if not _finite(timestamp) or abs(now - timestamp) > 10.0:
        errors.append(f"timestamp suspicious: {timestamp} (now={now:.1f})")
        s["timestamp"] = now
    else:
        s["timestamp"] = timestamp

    s["is_emergency"] = bool(is_emergency)
    s["is_drunk"] = bool(is_drunk)

    return (len(errors) == 0, s, errors)


# ═══════════════════════════════════════════════════════════════════════════
#  3. DETECTIE AGENTI INACTIVI (stale)
# ═══════════════════════════════════════════════════════════════════════════

class StaleAgentDetector:
    """Trackuieste ultimul mesaj primit de la fiecare agent.
       Returneaza agentii care nu au mai trimis nimic in AGENT_STALE_TIMEOUT."""

    def __init__(self, timeout: float = AGENT_STALE_TIMEOUT):
        self._timeout = timeout
        self._lock = threading.Lock()
        self._last_seen: Dict[str, float] = {}

    def touch(self, agent_id: str):
        with self._lock:
            self._last_seen[agent_id] = time.time()

    def stale_agents(self) -> list:
        now = time.time()
        with self._lock:
            return [aid for aid, ts in self._last_seen.items()
                    if now - ts > self._timeout]

    def remove(self, agent_id: str):
        with self._lock:
            self._last_seen.pop(agent_id, None)

    def reset(self):
        with self._lock:
            self._last_seen.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  4. RATE LIMITER  — anti-flood pe broadcast
# ═══════════════════════════════════════════════════════════════════════════

class RateLimiter:
    def __init__(self, max_per_sec: int = BROADCAST_RATE_LIMIT):
        self._max = max_per_sec
        self._lock = threading.Lock()
        self._buckets: Dict[str, list] = defaultdict(list)

    def allow(self, agent_id: str) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._buckets[agent_id]
            # evict old
            self._buckets[agent_id] = [t for t in bucket if now - t < 1.0]
            if len(self._buckets[agent_id]) >= self._max:
                return False
            self._buckets[agent_id].append(now)
            return True

    def reset(self):
        with self._lock:
            self._buckets.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  5. SANITIZARE OUTPUT CATRE FRONTEND (WebSocket / API)
# ═══════════════════════════════════════════════════════════════════════════

def _safe_str(val: Any, maxlen: int = MAX_STR_LEN) -> str:
    return str(val)[:maxlen] if val is not None else ""


def _safe_num(val: Any, default: float = 0.0) -> float:
    if isinstance(val, (int, float)) and _finite(val):
        return val
    return default


def sanitize_agent(raw: dict) -> dict:
    """Curata un dict agent inainte de trimitere la frontend."""
    return {
        "agent_id":     _safe_str(raw.get("agent_id"), MAX_ID_LEN),
        "agent_type":   raw.get("agent_type", "vehicle") if raw.get("agent_type") in VALID_AGENT_TYPES else "vehicle",
        "x":            round(_clamp(_safe_num(raw.get("x")), COORD_MIN, COORD_MAX), 2),
        "y":            round(_clamp(_safe_num(raw.get("y")), COORD_MIN, COORD_MAX), 2),
        "speed":        round(_clamp(_safe_num(raw.get("speed")), SPEED_MIN, SPEED_MAX), 2),
        "direction":    round(_safe_num(raw.get("direction")) % 360, 1),
        "intention":    _safe_str(raw.get("intention")),
        "risk_level":   raw.get("risk_level") if raw.get("risk_level") in VALID_RISKS else "low",
        "decision":     _safe_str(raw.get("decision")),
        "is_emergency": bool(raw.get("is_emergency")),
        "is_drunk":     bool(raw.get("is_drunk")),
        "timestamp":    round(_safe_num(raw.get("timestamp"), time.time()), 1),
        # campuri non-sensibile — stats
        **{k: raw[k] for k in ("reason", "llm_calls", "llm_errors",
                                "memory_decisions", "near_misses",
                                "v2x_alerts_received", "lessons_learned")
           if k in raw and isinstance(raw[k], (int, float, str))},
    }


def sanitize_full_state(raw: dict) -> dict:
    """Sanitizeaza starea completa inainte de WebSocket."""
    safe: dict = {
        "scenario": _safe_str(raw.get("scenario")) or None,
        "running":  bool(raw.get("running")),
    }

    # agents
    agents_raw = raw.get("agents") or {}
    safe["agents"] = {
        _safe_str(k, MAX_ID_LEN): sanitize_agent(v)
        for k, v in agents_raw.items() if isinstance(v, dict)
    }

    # infrastructure
    infra = raw.get("infrastructure") or {}
    if isinstance(infra, dict) and infra:
        safe["infrastructure"] = {
            "agent_id":        _safe_str(infra.get("agent_id"), MAX_ID_LEN),
            "phase":           _safe_str(infra.get("phase")),
            "phase_timer":     round(_safe_num(infra.get("phase_timer")), 1),
            "phase_remaining": round(_safe_num(infra.get("phase_remaining")), 1),
            "phase_duration":  round(_safe_num(infra.get("phase_duration"), 15), 1),
            "emergency_mode":  bool(infra.get("emergency_mode")),
            "emergency_axis":  _safe_str(infra.get("emergency_axis"), 10) or None,
            "recommendations": {
                _safe_str(vid, MAX_ID_LEN): {
                    "recommended_speed": round(_clamp(_safe_num(r.get("recommended_speed")), 0, SPEED_MAX), 1),
                    "action":            _safe_str(r.get("action")),
                    "signal":            _safe_str(r.get("signal"), 10),
                    "time_to_green":     round(_safe_num(r.get("time_to_green")), 1),
                }
                for vid, r in (infra.get("recommendations") or {}).items()
                if isinstance(r, dict)
            },
            "stats": {k: v for k, v in (infra.get("stats") or {}).items()
                      if isinstance(v, (int, float))},
        }
    else:
        safe["infrastructure"] = {}

    # collision_pairs (max 50)
    pairs = raw.get("collision_pairs") or []
    safe["collision_pairs"] = [
        {
            "agent1": _safe_str(p.get("agent1"), MAX_ID_LEN),
            "agent2": _safe_str(p.get("agent2"), MAX_ID_LEN),
            "risk":   p.get("risk") if p.get("risk") in VALID_RISKS else "low",
            "ttc":    round(_safe_num(p.get("ttc"), 999), 2),
        }
        for p in pairs[:50] if isinstance(p, dict)
    ]

    # stats
    safe["stats"] = {k: v for k, v in (raw.get("stats") or {}).items()
                     if isinstance(v, (int, float))}

    # grid info (intersections layout) — pass through validated
    grid_raw = raw.get("grid")
    if isinstance(grid_raw, dict):
        safe["grid"] = {
            "intersections": [
                {"x": round(_clamp(_safe_num(i.get("x")), COORD_MIN, COORD_MAX), 1),
                 "y": round(_clamp(_safe_num(i.get("y")), COORD_MIN, COORD_MAX), 1)}
                for i in (grid_raw.get("intersections") or []) if isinstance(i, dict)
            ],
            "grid_cols": int(_safe_num(grid_raw.get("grid_cols"), 1)),
            "grid_rows": int(_safe_num(grid_raw.get("grid_rows"), 1)),
            "grid_spacing": round(_safe_num(grid_raw.get("grid_spacing"), 300), 1),
            "demo_intersection": {
                "x": round(_clamp(_safe_num((grid_raw.get("demo_intersection") or {}).get("x")), COORD_MIN, COORD_MAX), 1),
                "y": round(_clamp(_safe_num((grid_raw.get("demo_intersection") or {}).get("y")), COORD_MIN, COORD_MAX), 1),
            },
        }

    # background traffic status
    safe["background_traffic"] = bool(raw.get("background_traffic"))

    # traffic light intersections
    tl_raw = raw.get("traffic_light_intersections") or []
    safe["traffic_light_intersections"] = [
        {
            "x": round(_clamp(_safe_num(tl.get("x")), COORD_MIN, COORD_MAX), 1),
            "y": round(_clamp(_safe_num(tl.get("y")), COORD_MIN, COORD_MAX), 1),
            "phase": _safe_str(tl.get("phase"), MAX_STR_LEN),
        }
        for tl in tl_raw[:20] if isinstance(tl, dict)
    ]

    safe["timestamp"] = round(time.time(), 1)
    return safe


# ═══════════════════════════════════════════════════════════════════════════
#  GLOBAL SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════

stale_detector = StaleAgentDetector()
broadcast_limiter = RateLimiter()

