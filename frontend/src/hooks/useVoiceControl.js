import { useState, useEffect, useRef, useCallback } from "react";

/**
 * useVoiceControl — Voice commands (Speech Recognition) + TTS alerts.
 *
 * Supported voice commands:
 *   "start [scenario]"  — start default scenario
 *   "stop"              — stop simulation
 *   "restart"           — restart simulation
 *   "zoom in"           — increase zoom
 *   "zoom out"          — decrease zoom
 *   "spawn drunk"       — spawn a drunk driver
 *   "traffic on/off"    — toggle background traffic
 *
 * TTS: speaks collision alerts when risk events appear.
 */

const SpeechRecognitionAPI = typeof window !== "undefined"
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null;

const synthSupported = typeof window !== "undefined" && "speechSynthesis" in window;

function _speak(message, rate = 1.2, volume = 0.7) {
  if (!synthSupported) return;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.rate = rate;
    utterance.volume = volume;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn("[VoiceControl] TTS error:", e);
  }
}

export function useVoiceControl({
  startScenario,
  stopSimulation,
  restartSimulation,
  spawnDrunkDriver,
  toggleBackgroundTraffic,
  setZoom,
  collisionPairs = [],
}) {
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [lastCommand, setLastCommand] = useState("");
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);
  const lastSpokenRef = useRef("");
  const voiceEnabledRef = useRef(false);
  const stoppedManuallyRef = useRef(false);
  const supported = !!SpeechRecognitionAPI;

  // Keep ref in sync
  useEffect(() => { voiceEnabledRef.current = voiceEnabled; }, [voiceEnabled]);

  // Store latest callbacks in refs so recognition effect doesn't re-run on every render
  const callbacksRef = useRef({
    startScenario, stopSimulation, restartSimulation,
    spawnDrunkDriver, toggleBackgroundTraffic, setZoom,
  });
  useEffect(() => {
    callbacksRef.current = {
      startScenario, stopSimulation, restartSimulation,
      spawnDrunkDriver, toggleBackgroundTraffic, setZoom,
    };
  }, [startScenario, stopSimulation, restartSimulation, spawnDrunkDriver, toggleBackgroundTraffic, setZoom]);

  const handleCommand = useCallback((text) => {
    const cb = callbacksRef.current;
    const confirm = (msg) => _speak(msg, 1.3, 0.5);

    let matched = true;

    if (text.includes("stop") && !text.includes("start")) {
      cb.stopSimulation?.();
      confirm("Simulation stopped");
    } else if (text.includes("restart") || text.includes("reset")) {
      cb.restartSimulation?.();
      confirm("Simulation restarted");
    } else if (text.includes("start")) {
      if (text.includes("blind")) cb.startScenario?.("blind_intersection");
      else if (text.includes("ambulance") || text.includes("emergency")) cb.startScenario?.("emergency_vehicle");
      else if (text.includes("drunk")) cb.startScenario?.("drunk_driver");
      else if (text.includes("traffic light") || text.includes("light")) cb.startScenario?.("multi_vehicle_traffic_light");
      else if (text.includes("right")) cb.startScenario?.("right_of_way");
      else cb.startScenario?.("multi_vehicle");
      confirm("Scenario started");
    } else if (text.includes("zoom in") || text.includes("closer")) {
      cb.setZoom?.(prev => Math.min(3.0, (prev || 0.7) + 0.2));
      confirm("Zooming in");
    } else if (text.includes("zoom out") || text.includes("further")) {
      cb.setZoom?.(prev => Math.max(0.15, (prev || 0.7) - 0.2));
      confirm("Zooming out");
    } else if (text.includes("drunk") || text.includes("spawn")) {
      cb.spawnDrunkDriver?.();
      confirm("Drunk driver spawned");
    } else if (text.includes("traffic")) {
      cb.toggleBackgroundTraffic?.();
      confirm("Background traffic toggled");
    } else {
      matched = false;
    }

    return matched;
  }, []);

  // ─── Speech Recognition ───────────────────────────────────
  useEffect(() => {
    if (!supported) return;

    // Turning OFF
    if (!voiceEnabled) {
      if (recognitionRef.current) {
        stoppedManuallyRef.current = true;
        try { recognitionRef.current.stop(); } catch (_) {}
        recognitionRef.current = null;
      }
      setListening(false);
      return;
    }

    // Turning ON — create fresh instance
    stoppedManuallyRef.current = false;
    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setListening(true);
    };

    recognition.onresult = (event) => {
      const last = event.results[event.results.length - 1];
      if (!last.isFinal) return;
      const transcript = last[0].transcript.trim().toLowerCase();
      console.log("[VoiceControl] heard:", transcript);
      setLastCommand(transcript);
      handleCommand(transcript);
    };

    recognition.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        console.error("[VoiceControl] Microphone permission denied");
        setVoiceEnabled(false);
        setListening(false);
        return;
      }
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("[VoiceControl] recognition error:", e.error);
      }
    };

    recognition.onend = () => {
      setListening(false);
      // Auto-restart if still enabled and not manually stopped
      if (voiceEnabledRef.current && !stoppedManuallyRef.current) {
        setTimeout(() => {
          if (voiceEnabledRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.start();
            } catch (e) {
              console.warn("[VoiceControl] restart failed:", e);
            }
          }
        }, 300);
      }
    };

    try {
      recognition.start();
    } catch (e) {
      console.error("[VoiceControl] Failed to start recognition:", e);
      setVoiceEnabled(false);
    }

    return () => {
      stoppedManuallyRef.current = true;
      try { recognition.stop(); } catch (_) {}
      recognitionRef.current = null;
      setListening(false);
    };
  }, [voiceEnabled, supported, handleCommand]);

  // ─── TTS for collision alerts ─────────────────────────────
  useEffect(() => {
    if (!ttsEnabled) return;
    if (!collisionPairs || collisionPairs.length === 0) {
      lastSpokenRef.current = "";
      return;
    }

    const collisions = collisionPairs.filter(p => p.risk === "collision" || p.risk === "high");
    if (collisions.length === 0) {
      lastSpokenRef.current = "";
      return;
    }

    const key = collisions.map(p => `${p.agent1}-${p.agent2}`).sort().join(",");
    if (key === lastSpokenRef.current) return;
    lastSpokenRef.current = key;

    const msg = collisions.length === 1
      ? `Collision risk between ${collisions[0].agent1} and ${collisions[0].agent2}`
      : `${collisions.length} collision risks detected`;
    _speak(msg, 1.0, 0.9);
  }, [collisionPairs, ttsEnabled]);

  // Cleanup TTS on unmount
  useEffect(() => {
    return () => {
      if (synthSupported) {
        try { window.speechSynthesis.cancel(); } catch (_) {}
      }
    };
  }, []);

  return {
    voiceEnabled,
    setVoiceEnabled,
    ttsEnabled,
    setTtsEnabled,
    lastCommand,
    listening,
    supported,
  };
}
