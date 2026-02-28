import React, { useEffect, useState } from "react";

export default function RiskAlert({ type, collisionPairs = [] }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (type !== "safe") {
      setVisible(true);
    } else {
      const timer = setTimeout(() => setVisible(false), 1000);
      return () => clearTimeout(timer);
    }
  }, [type]);

  if (!visible) return null;

  const isCollision = type === "collision";
  const bgColor = isCollision ? "#b71c1c" : "#e65100";
  const icon = isCollision ? "🚨" : "⚠️";
  const message = isCollision
    ? `IMMINENT COLLISION RISK!`
    : `HIGH RISK AHEAD!`;

  return (
    <div className="flex flex-col items-center justify-center p-4 rounded-xl shadow-2xl relative overflow-hidden" style={{
      background: bgColor,
      color: "#fff",
      animation: isCollision ? "pulse 0.5s infinite alternate" : "none",
    }}>
      <div className="flex items-center gap-3">
        <span className="text-3xl">{icon}</span>
        <div className="font-bold text-lg tracking-wider">{message}</div>
      </div>
      {collisionPairs && collisionPairs.length > 0 && (
        <div className="mt-2 text-sm opacity-90 font-mono text-center">
          {collisionPairs.map((p, i) => (
            <div key={i}>
              {p.agent1} ↔ {p.agent2} — TTC: {p.ttc}s
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
