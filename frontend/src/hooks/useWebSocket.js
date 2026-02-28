import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = `ws://${window.location.hostname}:8000/ws`;
const API_URL = `http://${window.location.hostname}:8000`;

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
    await fetch(`${API_URL}/simulation/start/${scenario}`, { method: "POST" });
  };

  const stopSimulation = async () => {
    await fetch(`${API_URL}/simulation/stop`, { method: "POST" });
  };

  const restartSimulation = async () => {
    await fetch(`${API_URL}/simulation/restart`, { method: "POST" });
  };

  const toggleBackgroundTraffic = async () => {
    const isActive = state?.background_traffic;
    const endpoint = isActive ? "stop" : "start";
    await fetch(`${API_URL}/background-traffic/${endpoint}`, { method: "POST" });
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
    toggleBackgroundTraffic, grid, backgroundTrafficActive,
  };
}
