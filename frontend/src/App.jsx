import React from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import IntersectionMap from "./components/IntersectionMap";
import VehicleStatus from "./components/VehicleStatus";
import RiskAlert from "./components/RiskAlert";

const SCENARIOS = [
  { id: "blind_intersection", label: "🏙 Intersectie Oarba", desc: "2 vehicule perpendiculare" },
  { id: "emergency_vehicle", label: "🚨 Vehicul Urgenta", desc: "Ambulanta vs vehicul normal" },
  { id: "multi_vehicle", label: "🚦 4 Vehicule", desc: "Toate directiile active" },
];

function StatBox({ label, value, color }) {
  return (
    <div style={{
      background: "#1e1e2e",
      border: "1px solid #333",
      borderRadius: "8px",
      padding: "10px 16px",
      textAlign: "center",
      minWidth: "90px",
    }}>
      <div style={{ color: color || "#00e676", fontSize: "22px", fontWeight: "bold", fontFamily: "monospace" }}>
        {value}
      </div>
      <div style={{ color: "#666", fontSize: "10px", fontFamily: "monospace", marginTop: "2px" }}>
        {label}
      </div>
    </div>
  );
}

export default function App() {
  const { state, connected, error, startScenario, stopSimulation, restartSimulation } = useWebSocket();

  const agents = state?.agents || {};
  const infrastructure = state?.infrastructure || {};
  const collisionPairs = state?.collision_pairs || [];
  const stats = state?.stats || {};
  const scenario = state?.scenario;
  const running = state?.running;

  const vehicleCount = Object.values(agents).filter(a => a.agent_type === "vehicle").length;

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0d0d1a",
      color: "#fff",
      fontFamily: "monospace",
      padding: "20px",
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "20px", color: "#00e676" }}>
            🚦 V2X Intersection Safety Agent
          </h1>
          <div style={{ color: "#555", fontSize: "11px", marginTop: "4px" }}>
            Cooperative Connected Vehicle Safety
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{
            width: "10px", height: "10px", borderRadius: "50%",
            background: connected ? "#00e676" : "#f44336",
            boxShadow: connected ? "0 0 8px #00e676" : "none",
          }} />
          <span style={{ color: connected ? "#00e676" : "#f44336", fontSize: "12px" }}>
            {connected ? "CONECTAT" : "DECONECTAT"}
          </span>
        </div>
      </div>

      {error && (
        <div style={{ background: "#1a0000", border: "1px solid #f44336", borderRadius: "8px", padding: "10px", marginBottom: "16px", color: "#f44336", fontSize: "12px" }}>
          ⚠ {error}
        </div>
      )}

      {/* Stats */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "20px", flexWrap: "wrap" }}>
        <StatBox label="VEHICULE" value={vehicleCount} color="#00e676" />
        <StatBox label="COLIZIUNI PREVENITE" value={stats.collisions_prevented || 0} color="#2196f3" />
        <StatBox label="TIMP" value={`${stats.elapsed_time || 0}s`} color="#9c27b0" />
        <StatBox
          label="SCENARIU"
          value={scenario ? scenario.replace("_", " ").toUpperCase() : "—"}
          color="#ff9800"
        />
        <StatBox
          label="STATUS"
          value={running ? "ACTIV" : "OPRIT"}
          color={running ? "#00e676" : "#f44336"}
        />
      </div>

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>

        {/* Harta */}
        <div>
          <RiskAlert collisionPairs={collisionPairs} />
          <IntersectionMap
            agents={agents}
            infrastructure={infrastructure}
            collisionPairs={collisionPairs}
          />

          {/* Butoane control */}
          <div style={{ marginTop: "14px" }}>
            <div style={{ color: "#555", fontSize: "10px", marginBottom: "8px", letterSpacing: "2px" }}>
              SCENARII
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {SCENARIOS.map(sc => (
                <button
                  key={sc.id}
                  onClick={() => startScenario(sc.id)}
                  style={{
                    background: scenario === sc.id && running ? "#00e676" : "#1e1e2e",
                    color: scenario === sc.id && running ? "#000" : "#ccc",
                    border: "1px solid #333",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontFamily: "monospace",
                  }}
                  title={sc.desc}
                >
                  {sc.label}
                </button>
              ))}
              <button
                onClick={stopSimulation}
                style={{
                  background: "#1e1e2e",
                  color: "#f44336",
                  border: "1px solid #f44336",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  cursor: "pointer",
                  fontSize: "12px",
                  fontFamily: "monospace",
                }}
              >
                ⏹ Stop
              </button>
              <button
                onClick={restartSimulation}
                style={{
                  background: "#1e1e2e",
                  color: "#ff9800",
                  border: "1px solid #ff9800",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  cursor: "pointer",
                  fontSize: "12px",
                  fontFamily: "monospace",
                }}
              >
                🔄 Restart
              </button>
            </div>
          </div>
        </div>

        {/* Panou dreapta */}
        <div style={{ flex: 1, minWidth: "240px", maxWidth: "320px" }}>
          <VehicleStatus agents={agents} infrastructure={infrastructure} />

          {/* Log conflicte */}
          {collisionPairs.length > 0 && (
            <div style={{
              background: "#1e1e2e",
              border: "1px solid #333",
              borderRadius: "8px",
              padding: "12px",
              marginTop: "12px",
            }}>
              <div style={{ color: "#aaa", fontSize: "10px", letterSpacing: "2px", marginBottom: "8px" }}>
                CONFLICTE ACTIVE
              </div>
              {collisionPairs.map((p, i) => (
                <div key={i} style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  padding: "4px 0",
                  borderBottom: "1px solid #222",
                  color: p.risk === "collision" ? "#f44336" : "#ff9800",
                }}>
                  <span>{p.agent1} ↔ {p.agent2}</span>
                  <span>{p.ttc}s | {p.risk.toUpperCase()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          from { opacity: 1; }
          to { opacity: 0.6; }
        }
        button:hover { opacity: 0.85; transform: translateY(-1px); transition: 0.15s; }
      `}</style>
    </div>
  );
}
