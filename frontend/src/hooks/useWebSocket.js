import { useState, useEffect, useRef, useCallback } from "react";

const API_TOKEN = import.meta.env.VITE_API_TOKEN || "v2x-secret-token-change-in-prod";
const WS_URL = `ws://${window.location.hostname}:8000/ws?token=${encodeURIComponent(API_TOKEN)}`;
const API_URL = `http://${window.location.hostname}:8000`;

const authHeaders = {
  "Content-Type": "application/json",
  "Authorization": `Bearer ${API_TOKEN}`,
};

export function useWebSocket() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(data);
        } catch (e) {
          console.error("WS parse error:", e);
        }
      };

      ws.onerror = () => {
        setError("Cannot connect to server. Check if backend is running.");
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 2000);
      };
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const startScenario = async (scenario) => {
    await fetch(`${API_URL}/simulation/start/${scenario}`, { method: "POST", headers: authHeaders });
  };

  const stopSimulation = async () => {
    await fetch(`${API_URL}/simulation/stop`, { method: "POST", headers: authHeaders });
  };

  const restartSimulation = async () => {
    await fetch(`${API_URL}/simulation/restart`, { method: "POST", headers: authHeaders });
  };

  const toggleBackgroundTraffic = async () => {
    const isActive = state?.background_traffic;
    const endpoint = isActive ? "stop" : "start";
    await fetch(`${API_URL}/background-traffic/${endpoint}`, { method: "POST", headers: authHeaders });
  };

  const spawnDrunkDriver = async () => {
    await fetch(`${API_URL}/simulation/spawn-drunk`, { method: "POST", headers: authHeaders });
  };

  const spawnPolice = async () => {
    await fetch(`${API_URL}/simulation/spawn-police`, { method: "POST", headers: authHeaders });
  };

  const spawnAmbulance = async () => {
    await fetch(`${API_URL}/simulation/spawn-ambulance`, { method: "POST", headers: authHeaders });
  };

  const initMode = async (mode) => {
    await fetch(`${API_URL}/simulation/init`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ mode }),
    });
  };

  const agents = state?.agents || {};
  const collisionPairs = state?.collision_pairs || [];
  const grid = state?.grid || null;
  const backgroundTrafficActive = state?.background_traffic || false;

  const status = collisionPairs.some(p => p.risk === "collision" || p.risk === "high")
    ? "collision"
    : "safe";

  return {
    state, connected, error, agents, status, collisionPairs,
    startScenario, stopSimulation, restartSimulation,
    toggleBackgroundTraffic, spawnDrunkDriver, spawnPolice, spawnAmbulance, grid, backgroundTrafficActive,
    initMode,
  };
}
