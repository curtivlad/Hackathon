import { useState, useEffect, useRef, useCallback } from "react";


const SpeechRecognitionAPI =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

const synthSupported =
  typeof window !== "undefined" && "speechSynthesis" in window;

let _ttsUnlocked = false;
const _ttsQueue = [];
let _ttsSpeaking = false;

function _unlockTTS() {
  if (_ttsUnlocked || !synthSupported) return;
  try {
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    u.rate = 10;
    window.speechSynthesis.speak(u);
    setTimeout(() => {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }, 50);
    _ttsUnlocked = true;
  } catch (_) {}
}

function _processQueue() {
  if (_ttsSpeaking || _ttsQueue.length === 0 || !synthSupported) return;

  const { message, rate, volume } = _ttsQueue.shift();
  _ttsSpeaking = true;

  try {
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(message);
    utterance.rate = rate;
    utterance.volume = volume;
    utterance.pitch = 1.0;
    utterance.lang = "en-US";

    const resumeInterval = setInterval(() => {
      if (!window.speechSynthesis.speaking) {
        clearInterval(resumeInterval);
        return;
      }
      try { window.speechSynthesis.resume(); } catch (_) {}
    }, 10000);

    const cleanup = () => {
      clearInterval(resumeInterval);
      _ttsSpeaking = false;
      setTimeout(_processQueue, 200);
    };

    utterance.onend = cleanup;
    utterance.onerror = cleanup;

    window.speechSynthesis.speak(utterance);

    setTimeout(() => {
      if (_ttsSpeaking) {
        try { window.speechSynthesis.cancel(); } catch (_) {}
        cleanup();
      }
    }, 15000);
  } catch (e) {
    console.warn("[VoiceControl] TTS error:", e);
    _ttsSpeaking = false;
    setTimeout(_processQueue, 500);
  }
}

function _speak(message, rate = 1.2, volume = 0.7) {
  if (!synthSupported) return;
  if (_ttsQueue.length >= 3) _ttsQueue.shift();
  _ttsQueue.push({ message, rate, volume });
  _processQueue();
}

function _cancelAllTTS() {
  _ttsQueue.length = 0;
  _ttsSpeaking = false;
  if (synthSupported) {
    try { window.speechSynthesis.cancel(); } catch (_) {}
  }
}

export function useVoiceControl({
  startScenario,
  stopSimulation,
  restartSimulation,
  spawnDrunkDriver,
  spawnPolice,
  toggleBackgroundTraffic,
  setZoom,
  collisionPairs = [],
}) {
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [ttsEnabled, setTtsEnabledRaw] = useState(false);
  const [lastCommand, setLastCommand] = useState("");
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);
  const lastSpokenAlertRef = useRef("");
  const voiceEnabledRef = useRef(false);
  const stoppedManuallyRef = useRef(false);
  const ttsCooldownRef = useRef(0);
  const restartTimeoutRef = useRef(null);
  const commandCooldownRef = useRef(0);
  const supported = !!SpeechRecognitionAPI;


  const setTtsEnabled = useCallback((valOrFn) => {
    setTtsEnabledRaw((prev) => {
      const next = typeof valOrFn === "function" ? valOrFn(prev) : valOrFn;
      if (next && !prev) {
        _unlockTTS();
        lastSpokenAlertRef.current = "";
        ttsCooldownRef.current = 0;
      }
      if (!next) _cancelAllTTS();
      return next;
    });
  }, []);

  useEffect(() => { voiceEnabledRef.current = voiceEnabled; }, [voiceEnabled]);

  const callbacksRef = useRef({
    startScenario, stopSimulation, restartSimulation,
    spawnDrunkDriver, spawnPolice, toggleBackgroundTraffic, setZoom,
  });
  useEffect(() => {
    callbacksRef.current = {
      startScenario, stopSimulation, restartSimulation,
      spawnDrunkDriver, spawnPolice, toggleBackgroundTraffic, setZoom,
    };
  }, [startScenario, stopSimulation, restartSimulation, spawnDrunkDriver, spawnPolice, toggleBackgroundTraffic, setZoom]);

  const handleCommand = useCallback((text) => {
    const now = Date.now();
    if (now - commandCooldownRef.current < 1000) return false;

    const cb = callbacksRef.current;
    const confirm = (msg) => _speak(msg, 1.3, 0.6);

    const t = text.toLowerCase().trim().replace(/[.,!?;:]/g, "");

    let matched = true;

    if ((t.includes("stop") || t.includes("opreste")) && !t.includes("start")) {
      cb.stopSimulation?.();
      confirm("Simulation stopped");

    } else if (t.includes("restart") || t.includes("reset") || t.includes("restarteaza")) {
      cb.restartSimulation?.();
      confirm("Simulation restarted");

    } else if (t.includes("start") || t.includes("porneste") || t.includes("incepe")) {
      let scenario = "right_of_way";
      if (t.includes("ambulance") || t.includes("ambulanta") || t.includes("emergency") || t.includes("urgenta")) {
        scenario = "emergency_vehicle";
      } else if (t.includes("drunk") || t.includes("beat")) {
        scenario = "drunk_driver";
      } else if (t.includes("traffic light") || t.includes("light") || t.includes("semafor")) {
        scenario = "multi_vehicle_traffic_light";
      } else if (t.includes("right") || t.includes("prioritate") || t.includes("dreapta")) {
        scenario = "right_of_way";
      } else if (t.includes("no light") || t.includes("fara semafor")) {
        scenario = "emergency_vehicle_no_lights";
      }
      cb.startScenario?.(scenario);
      confirm("Scenario started");

    } else if (t.includes("zoom in") || t.includes("closer") || t.includes("mareste")) {
      cb.setZoom?.((prev) => Math.min(3.0, (prev || 0.7) + 0.2));
      confirm("Zooming in");
    } else if (t.includes("zoom out") || t.includes("further") || t.includes("micsoreaza")) {
      cb.setZoom?.((prev) => Math.max(0.15, (prev || 0.7) - 0.2));
      confirm("Zooming out");

    } else if (t.includes("police") || t.includes("politie") || t.includes("politia")) {
      cb.spawnPolice?.();
      confirm("Police car spawned");

    } else if (t.includes("spawn") || (t.includes("drunk") && !t.includes("start"))) {
      cb.spawnDrunkDriver?.();
      confirm("Drunk driver spawned");

    } else if (t.includes("traffic") || t.includes("trafic")) {
      cb.toggleBackgroundTraffic?.();
      confirm("Background traffic toggled");

    } else {
      matched = false;
    }

    if (matched) commandCooldownRef.current = now;
    return matched;
  }, []);

  useEffect(() => {
    if (!supported) return;

    if (restartTimeoutRef.current) {
      clearTimeout(restartTimeoutRef.current);
      restartTimeoutRef.current = null;
    }

    if (!voiceEnabled) {
      if (recognitionRef.current) {
        stoppedManuallyRef.current = true;
        try { recognitionRef.current.abort(); } catch (_) {}
        recognitionRef.current = null;
      }
      setListening(false);
      return;
    }

    stoppedManuallyRef.current = false;

    function createAndStart() {
      if (!voiceEnabledRef.current || stoppedManuallyRef.current) return;

      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
      }

      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 3;

      recognitionRef.current = recognition;

      recognition.onstart = () => {
        if (voiceEnabledRef.current) setListening(true);
      };

      recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (!result.isFinal) continue;

          let bestTranscript = "";
          let commandMatched = false;

          for (let alt = 0; alt < result.length; alt++) {
            const transcript = result[alt].transcript.trim().toLowerCase();
            if (!bestTranscript) bestTranscript = transcript;
            if (handleCommand(transcript)) {
              commandMatched = true;
              bestTranscript = transcript;
              break;
            }
          }

          console.log("[VoiceControl] heard:", bestTranscript, commandMatched ? "✓" : "✗");
          setLastCommand(bestTranscript);
        }
      };

      recognition.onerror = (e) => {
        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
          console.error("[VoiceControl] Microphone permission denied");
          stoppedManuallyRef.current = true;
          setVoiceEnabled(false);
          setListening(false);
          return;
        }
      };

      recognition.onend = () => {
        setListening(false);
        if (voiceEnabledRef.current && !stoppedManuallyRef.current) {
          if (restartTimeoutRef.current) clearTimeout(restartTimeoutRef.current);
          restartTimeoutRef.current = setTimeout(() => {
            restartTimeoutRef.current = null;
            if (voiceEnabledRef.current && !stoppedManuallyRef.current) {
              createAndStart(); // Fresh instance is more reliable
            }
          }, 500);
        }
      };

      try {
        recognition.start();
      } catch (e) {
        console.warn("[VoiceControl] start failed, retrying:", e.message);
        restartTimeoutRef.current = setTimeout(() => {
          if (voiceEnabledRef.current && !stoppedManuallyRef.current) {
            createAndStart();
          }
        }, 1000);
      }
    }

    createAndStart();

    return () => {
      stoppedManuallyRef.current = true;
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
        restartTimeoutRef.current = null;
      }
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
        recognitionRef.current = null;
      }
      setListening(false);
    };
  }, [voiceEnabled, supported, handleCommand]);

  useEffect(() => {
    if (!ttsEnabled) return;
    if (!collisionPairs || collisionPairs.length === 0) return;

    const dangers = collisionPairs.filter(
      (p) => p.risk === "collision" || p.risk === "high"
    );
    if (dangers.length === 0) return;

    const key = dangers.map((p) => `${p.agent1}-${p.agent2}-${p.risk}`).sort().join("|");
    if (key === lastSpokenAlertRef.current) return;

    const now = Date.now();
    if (now - ttsCooldownRef.current < 4000) return;
    ttsCooldownRef.current = now;
    lastSpokenAlertRef.current = key;

    const collisions = dangers.filter((p) => p.risk === "collision");
    const highRisks = dangers.filter((p) => p.risk === "high");

    let msg;
    if (collisions.length > 0) {
      const pair = collisions[0];
      msg = `Collision warning! ${pair.agent1} and ${pair.agent2} are about to collide!`;
      if (collisions.length > 1) msg += ` ${collisions.length} total collision risks.`;
    } else {
      msg = `Caution. ${highRisks.length} high risk ${highRisks.length === 1 ? "situation" : "situations"} detected.`;
    }

    _speak(msg, 1.0, 1.0);
  }, [collisionPairs, ttsEnabled]);

  useEffect(() => {
    return () => { _cancelAllTTS(); };
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
