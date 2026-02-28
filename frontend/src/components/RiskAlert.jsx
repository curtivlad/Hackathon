import React, { useEffect, useState, useRef } from "react";
import { AlertTriangle } from "lucide-react";

const MIN_DISPLAY_MS = 3000;

export default function RiskAlert({ type, collisionPairs = [] }) {
  const [visible, setVisible] = useState(false);
  const [displayData, setDisplayData] = useState({ type: "safe", pairs: [] });
  const showTimestamp = useRef(0);
  const hideTimer = useRef(null);

  useEffect(() => {
    if (type !== "safe") {
      if (hideTimer.current) {
        clearTimeout(hideTimer.current);
        hideTimer.current = null;
      }
      showTimestamp.current = Date.now();
      setDisplayData({ type, pairs: collisionPairs });
      setVisible(true);
    } else if (visible) {
      const elapsed = Date.now() - showTimestamp.current;
      const remaining = Math.max(0, MIN_DISPLAY_MS - elapsed);
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(() => {
        setVisible(false);
        hideTimer.current = null;
      }, remaining);
    }
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, [type, collisionPairs]);

  if (!visible) return null;

  const isCollision = displayData.type === "collision";
  const bgColor = isCollision ? "rgba(183, 28, 28, 0.95)" : "rgba(230, 81, 0, 0.95)";
  const message = isCollision
    ? "IMMINENT COLLISION RISK"
    : "HIGH RISK AHEAD";

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-lg pointer-events-none">
      <div
        className="flex flex-col items-center justify-center p-4 rounded-xl shadow-2xl overflow-hidden pointer-events-auto"
        style={{
          background: bgColor,
          color: "#fff",
          backdropFilter: "blur(8px)",
          animation: isCollision ? "pulse 0.5s infinite alternate" : "none",
        }}
      >
        <div className="flex items-center gap-3">
          <AlertTriangle size={28} className="text-white" />
          <div className="font-bold text-lg tracking-wider">{message}</div>
        </div>
        {displayData.pairs && displayData.pairs.length > 0 && (
          <div className="mt-2 text-sm opacity-90 font-mono text-center">
            {displayData.pairs.map((p, i) => (
              <div key={i}>
                {p.agent1} -- {p.agent2} | TTC: {p.ttc}s
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
