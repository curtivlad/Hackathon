import React, { useState, useEffect, useRef } from "react";
import { Radio } from "lucide-react";

const API_URL = `http://${window.location.hostname}:8000`;

export default function V2XLog() {
  const [history, setHistory] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/v2x/history?last_n=30`);
        const data = await res.json();
        setHistory(data.history || []);
      } catch {
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  const riskColor = (risk) => {
    switch (risk) {
      case "collision": return "#f44336";
      case "high": return "#ff5722";
      case "medium": return "#ff9800";
      default: return "#4caf50";
    }
  };

  const decisionColor = (dec) => {
    switch (dec) {
      case "stop": return "#f44336";
      case "brake": return "#ff9800";
      case "yield": return "#ffeb3b";
      case "go": return "#00e676";
      default: return "#888";
    }
  };

  return (
    <div className="rounded-2xl border border-white/10 overflow-hidden"
      style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(16px)' }}>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-2">
          <Radio size={14} className="text-cyan-500" />
          <span className="text-xs font-bold text-neutral-300 tracking-wider">
            V2X CHANNEL LOG
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-neutral-500">
            {history.length} msgs
          </span>
          <span className="text-neutral-600 text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded && (
        <div
          ref={scrollRef}
          className="px-3 pb-3 overflow-y-auto"
          style={{ maxHeight: "180px" }}
        >
          {history.length === 0 ? (
            <div className="text-neutral-600 text-xs font-mono py-2 text-center">
              No V2X messages yet. Start a scenario.
            </div>
          ) : (
            history.slice().reverse().map((msg, i) => (
              <div key={i} className="flex items-center gap-2 py-0.5 border-b border-white/5 last:border-0">
                <span className="text-neutral-600 font-mono" style={{ fontSize: "9px", minWidth: "55px" }}>
                  {new Date(msg.timestamp * 1000).toLocaleTimeString()}
                </span>
                <span
                  className="font-mono font-bold"
                  style={{
                    fontSize: "10px",
                    color: msg.is_emergency ? "#ff1744" : "#4fc3f7",
                    minWidth: "70px",
                  }}
                >
                  {msg.is_emergency ? "[EMR] " : ""}{msg.agent_id}
                </span>
                <span className="font-mono text-neutral-500" style={{ fontSize: "9px" }}>
                  ({msg.x?.toFixed(0)},{msg.y?.toFixed(0)})
                </span>
                <span className="font-mono text-neutral-400" style={{ fontSize: "9px" }}>
                  {(msg.speed * 3.6)?.toFixed(0)}km/h
                </span>
                <span
                  className="font-mono font-bold"
                  style={{ fontSize: "9px", color: decisionColor(msg.decision) }}
                >
                  {msg.decision?.toUpperCase()}
                </span>
                {msg.risk_level && msg.risk_level !== "low" && (
                  <span
                    className="font-mono font-bold"
                    style={{ fontSize: "9px", color: riskColor(msg.risk_level) }}
                  >
                    {msg.risk_level?.toUpperCase()}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

