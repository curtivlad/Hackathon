import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

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
        setError("Nu se poate conecta la server. Verifica ca backend-ul ruleaza.");
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconecteaza dupa 2 secunde
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

  // Functii de control API
  const startScenario = async (scenario) => {
    await fetch(`${API_URL}/simulation/start/${scenario}`, { method: "POST" });
  };

  const stopSimulation = async () => {
    await fetch(`${API_URL}/simulation/stop`, { method: "POST" });
  };

  const restartSimulation = async () => {
    await fetch(`${API_URL}/simulation/restart`, { method: "POST" });
  };

  return { state, connected, error, startScenario, stopSimulation, restartSimulation };
}
