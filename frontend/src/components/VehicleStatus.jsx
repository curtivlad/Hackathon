import React from "react";

const DECISION_COLORS = {
  go: "#00e676",
  yield: "#ffeb3b",
  brake: "#ff9800",
  stop: "#f44336",
};

const RISK_COLORS = {
  low: "#4caf50",
  medium: "#ff9800",
  high: "#ff5722",
  collision: "#f44336",
};

function VehicleCard({ agent }) {
  const decisionColor = DECISION_COLORS[agent.decision] || "#aaa";
  const riskColor = RISK_COLORS[agent.risk_level] || "#aaa";
  const speedKmh = (agent.speed * 3.6).toFixed(1);

  return (
    <div style={{
      background: "#1a1a1a",
      border: `1px solid ${decisionColor}44`,
      borderLeft: `4px solid ${decisionColor}`,
      borderRadius: "8px",
      padding: "12px",
      marginBottom: "8px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ color: "#fff", fontWeight: "bold", fontFamily: "monospace" }}>
          {agent.is_emergency ? "[EMR] " : ""}{agent.agent_id}
        </span>
        <span style={{
          background: decisionColor + "33",
          color: decisionColor,
          padding: "2px 8px",
          borderRadius: "4px",
          fontSize: "12px",
          fontWeight: "bold",
          fontFamily: "monospace",
        }}>
          {agent.decision?.toUpperCase()}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "8px" }}>
        <Stat label="Speed" value={`${speedKmh} km/h`} />
        <Stat label="Heading" value={`${agent.direction}`} />
        <Stat label="X" value={`${agent.x?.toFixed(1)}m`} />
        <Stat label="Y" value={`${agent.y?.toFixed(1)}m`} />
        <div style={{ gridColumn: "span 2" }}>
          <Stat
            label="Risk"
            value={agent.risk_level?.toUpperCase()}
            valueColor={riskColor}
          />
        </div>
        {agent.reason && agent.reason !== "clear" && (
          <div style={{ gridColumn: "span 2" }}>
            <Stat label="Reason" value={agent.reason} />
          </div>
        )}
        {(agent.llm_calls !== undefined && agent.llm_calls > 0) && (
          <div style={{ gridColumn: "span 2" }}>
            <Stat
              label="🧠 AI Brain"
              value={`${agent.llm_calls} decizii LLM`}
              valueColor="#7c4dff"
            />
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, valueColor }) {
  return (
    <div>
      <div style={{ color: "#666", fontSize: "10px", fontFamily: "monospace" }}>{label}</div>
      <div style={{ color: valueColor || "#ccc", fontSize: "12px", fontFamily: "monospace", fontWeight: "bold" }}>
        {value}
      </div>
    </div>
  );
}

function VehicleCardCompact({ agent }) {
  const decisionColor = DECISION_COLORS[agent.decision] || "#aaa";
  const riskColor = RISK_COLORS[agent.risk_level] || "#aaa";
  const speedKmh = (agent.speed * 3.6).toFixed(0);

  return (
    <div style={{
      background: "#141414",
      border: `1px solid ${decisionColor}33`,
      borderLeft: `3px solid ${decisionColor}`,
      borderRadius: "6px",
      padding: "8px 10px",
      marginBottom: "5px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <span style={{ color: "#aaa", fontFamily: "monospace", fontSize: "11px", fontWeight: "bold" }}>
        {agent.is_emergency ? "🚑 " : ""}{agent.agent_id}
      </span>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <span style={{ color: "#777", fontFamily: "monospace", fontSize: "10px" }}>
          {speedKmh} km/h
        </span>
        <span style={{
          color: riskColor,
          fontFamily: "monospace", fontSize: "10px", fontWeight: "bold",
        }}>
          {agent.risk_level !== "low" ? agent.risk_level?.toUpperCase() : ""}
        </span>
        <span style={{
          background: decisionColor + "33",
          color: decisionColor,
          padding: "1px 6px",
          borderRadius: "3px",
          fontSize: "10px",
          fontWeight: "bold",
          fontFamily: "monospace",
        }}>
          {agent.decision?.toUpperCase()}
        </span>
        {agent.reason && agent.reason !== "clear" && agent.reason !== "waypoint" && (
          <span style={{ color: "#555", fontFamily: "monospace", fontSize: "9px" }}>
            {agent.reason}
          </span>
        )}
      </div>
    </div>
  );
}

export default function VehicleStatus({ agents = {}, infrastructure = {} }) {
  const vehicles = Object.values(agents).filter(
    a => a.agent_type === "vehicle" && !a.agent_id?.startsWith("BG_")
  );
  const bgVehicles = Object.values(agents).filter(
    a => a.agent_type === "vehicle" && a.agent_id?.startsWith("BG_")
  );

  return (
    <div>
      <h3 style={{ color: "#aaa", fontSize: "12px", fontFamily: "monospace", marginBottom: "10px", letterSpacing: "2px" }}>
        DEMO VEHICLES ({vehicles.length})
      </h3>

      {vehicles.length === 0 ? (
        <div style={{ color: "#555", fontFamily: "monospace", fontSize: "12px" }}>
          No active vehicles. Start a scenario.
        </div>
      ) : (
        vehicles.map(v => <VehicleCard key={v.agent_id} agent={v} />)
      )}

      {bgVehicles.length > 0 && (
        <>
          <h3 style={{ color: "#666", fontSize: "11px", fontFamily: "monospace", marginTop: "16px", marginBottom: "8px", letterSpacing: "2px" }}>
            BACKGROUND TRAFFIC ({bgVehicles.length})
          </h3>
          {bgVehicles.map(v => <VehicleCardCompact key={v.agent_id} agent={v} />)}
        </>
      )}

      {infrastructure.phase && (
        <div style={{
          background: "#1a1a1a",
          border: "1px solid #333",
          borderRadius: "8px",
          padding: "12px",
          marginTop: "12px",
        }}>
          <div style={{ color: "#aaa", fontSize: "10px", fontFamily: "monospace", marginBottom: "8px", letterSpacing: "2px" }}>
            SMART TRAFFIC LIGHT
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{
              color: "#fff", fontFamily: "monospace", fontSize: "13px", fontWeight: "bold"
            }}>
              {infrastructure.phase === "NS_GREEN" ? "N/S GREEN | E/W RED" : "N/S RED | E/W GREEN"}
            </span>
            <span style={{ color: "#666", fontFamily: "monospace", fontSize: "11px" }}>
              {infrastructure.phase_remaining}s
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
