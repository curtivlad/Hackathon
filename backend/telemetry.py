"""
telemetry.py — Colector de telemetrie si rapoarte de performanta.

Colecteaza metrici non-sensibile despre cooperarea vehiculelor:
- Coliziuni prevenite
- Throughput intersectie (vehicule/minut)
- Breakdown riscuri pe tip
- Scor de cooperare (0-100)
- Evenimente V2X
- Export rapoarte in fisiere JSON (persistenta)

Nu stocheaza date de localizare sau telemetrie bruta —
doar statistici agregate.
"""

import os
import json
import time
import threading
import logging
from collections import defaultdict
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("telemetry")

# Directory for exported telemetry reports
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "telemetry_reports")
os.makedirs(EXPORT_DIR, exist_ok=True)


class TelemetryCollector:
    """Colecteaza si agreg metrici de performanta ale intersectiei."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events: List[dict] = []
        self._max_events = 1000
        self._collisions_prevented = 0
        self._vehicles_passed = 0
        self._total_v2x_messages = 0
        self._risk_events: Dict[str, int] = defaultdict(int)
        self._negotiation_times: List[float] = []
        self._start_time = time.time()
        self._scenario_history: List[dict] = []
        self._active_scenario: Optional[str] = None
        self._report_history: List[dict] = []  # stored report snapshots

    def record_event(self, event_type: str, data: Optional[dict] = None):
        """Inregistreaza un eveniment de telemetrie."""
        with self._lock:
            entry = {
                "type": event_type,
                "timestamp": time.time(),
                "data": data or {},
            }
            self._events.append(entry)
            if len(self._events) > self._max_events:
                self._events.pop(0)

            # Update aggregate counters
            if event_type == "collision_prevented":
                self._collisions_prevented += 1
            elif event_type == "vehicle_passed":
                self._vehicles_passed += 1
            elif event_type == "v2x_message":
                self._total_v2x_messages += 1
            elif event_type == "risk_detected":
                level = (data or {}).get("level", "unknown")
                self._risk_events[level] += 1
            elif event_type == "negotiation_complete":
                duration_ms = (data or {}).get("duration_ms", 0)
                self._negotiation_times.append(duration_ms)
                if len(self._negotiation_times) > 200:
                    self._negotiation_times.pop(0)

    def record_scenario_start(self, scenario: str):
        """Inregistreaza inceputul unui scenariu."""
        with self._lock:
            self._active_scenario = scenario
            self._scenario_history.append({
                "scenario": scenario,
                "started_at": time.time(),
                "ended_at": None,
            })

    def record_scenario_end(self):
        """Inregistreaza sfarsitul scenariului curent."""
        with self._lock:
            if self._scenario_history:
                self._scenario_history[-1]["ended_at"] = time.time()
            self._active_scenario = None

    def generate_report(self) -> dict:
        """Genereaza un raport complet de performanta."""
        with self._lock:
            elapsed = time.time() - self._start_time
            minutes = max(elapsed / 60.0, 0.01)

            avg_negotiation = 0.0
            if self._negotiation_times:
                avg_negotiation = sum(self._negotiation_times) / len(self._negotiation_times)

            return {
                "session_duration_s": round(elapsed, 1),
                "collisions_prevented": self._collisions_prevented,
                "vehicles_passed": self._vehicles_passed,
                "total_v2x_messages": self._total_v2x_messages,
                "throughput_vehicles_per_min": round(
                    self._vehicles_passed / minutes, 1
                ),
                "avg_negotiation_time_ms": round(avg_negotiation, 1),
                "risk_breakdown": dict(self._risk_events),
                "cooperation_score": self._calculate_cooperation_score(),
                "total_events": len(self._events),
                "active_scenario": self._active_scenario,
                "scenarios_run": len(self._scenario_history),
                "recent_events": [
                    {"type": e["type"], "timestamp": round(e["timestamp"], 1)}
                    for e in self._events[-20:]
                ],
            }

    def _calculate_cooperation_score(self) -> float:
        """
        Scor 0-100 care masoara cat de bine au cooperat agentii.

        Formula:
        - Baza 50 puncte
        - +25 daca au fost coliziuni prevenite
        - +25 proportional cu raportul prevented/total_risks
        - -10 pentru fiecare eveniment collision nerezolvat
        """
        score = 50.0

        total_risks = sum(self._risk_events.values())
        collisions = self._risk_events.get("collision", 0)

        if self._collisions_prevented > 0:
            score += 25.0

        if total_risks > 0:
            prevention_rate = self._collisions_prevented / max(total_risks, 1)
            score += 25.0 * min(1.0, prevention_rate)

        # Penalizeaza coliziunile neprevenite
        score -= collisions * 5.0

        return round(max(0.0, min(100.0, score)), 1)

    def export_to_file(self, path: Optional[str] = None) -> str:
        """Exporta raportul curent intr-un fisier JSON.
        Returneaza calea fisierului creat."""
        report = self.generate_report()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"telemetry_{timestamp}.json"
        filepath = path or os.path.join(EXPORT_DIR, filename)

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        # Store in report history
        with self._lock:
            self._report_history.append({
                "filename": filename,
                "filepath": filepath,
                "exported_at": time.time(),
                "report": report,
            })
            # Keep only last 50 reports in memory
            if len(self._report_history) > 50:
                self._report_history = self._report_history[-50:]

        logger.info(f"Telemetry report exported to {filepath}")
        return filepath

    def get_history(self, last_n: int = 10) -> List[dict]:
        """Returneaza ultimele N rapoarte exportate."""
        with self._lock:
            history = self._report_history[-last_n:]

        # Also try to load from disk if memory is empty
        if not history:
            try:
                files = sorted(
                    [f for f in os.listdir(EXPORT_DIR) if f.endswith(".json")],
                    reverse=True
                )[:last_n]
                for fn in files:
                    filepath = os.path.join(EXPORT_DIR, fn)
                    try:
                        with open(filepath, "r") as f:
                            report = json.load(f)
                        history.append({
                            "filename": fn,
                            "filepath": filepath,
                            "report": report,
                        })
                    except (json.JSONDecodeError, IOError):
                        continue
            except FileNotFoundError:
                pass

        return history

    def reset(self):
        """Reseteaza telemetria (la restart sesiune)."""
        with self._lock:
            self._events.clear()
            self._collisions_prevented = 0
            self._vehicles_passed = 0
            self._total_v2x_messages = 0
            self._risk_events.clear()
            self._negotiation_times.clear()
            self._start_time = time.time()
            self._scenario_history.clear()
            self._active_scenario = None


# Global singleton
telemetry = TelemetryCollector()

