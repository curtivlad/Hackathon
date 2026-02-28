import React, { useEffect, useState } from "react";

export default function RiskAlert({ collisionPairs = [] }) {
  const [visible, setVisible] = useState(false);

  const hasCollision = collisionPairs.some(p => p.risk === "collision");
  const hasHigh = collisionPairs.some(p => p.risk === "high");

  useEffect(() => {
    if (hasCollision || hasHigh) {
      setVisible(true);
    } else {
      const timer = setTimeout(() => setVisible(false), 1000);
      return () => clearTimeout(timer);
    }
  }, [hasCollision, hasHigh]);

  if (!visible) return null;

  const bgColor = hasCollision ? "#b71c1c" : "#e65100";
  const icon = hasCollision ? "🚨" : "⚠️";
  const message = hasCollision
    ? `RISC COLIZIUNE IMINENT — ${collisionPairs.filter(p => p.risk === "collision").length} pereche(i) detectate`
    : `RISC RIDICAT — ${collisionPairs.length} conflict(e) active`;

  return (
    <div style={{
      background: bgColor,
      color: "#fff",
      padding: "10px 16px",
      borderRadius: "8px",
      fontFamily: "monospace",
      fontWeight: "bold",
      fontSize: "13px",
      display: "flex",
      alignItems: "center",
      gap: "10px",
      animation: hasCollision ? "pulse 0.5s infinite alternate" : "none",
      marginBottom: "12px",
    }}>
      <span style={{ fontSize: "20px" }}>{icon}</span>
      <div>
        <div>{message}</div>
        {collisionPairs.map((p, i) => (
          <div key={i} style={{ fontSize: "11px", opacity: 0.85, marginTop: "2px" }}>
            {p.agent1} ↔ {p.agent2} — TTC: {p.ttc}s
          </div>
        ))}
      </div>
    </div>
  );
}
