import React, { useState, useEffect, useRef } from "react";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

const MAX_EVENTS = 50;

export default function EventLog({ collisionPairs = [], agents = {} }) {
  const [events, setEvents] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef(null);
  const prevPairsRef = useRef("");

  useEffect(() => {
    if (!collisionPairs || collisionPairs.length === 0) return;

    const key = collisionPairs
      .map((p) => `${p.agent1}-${p.agent2}-${p.risk}`)
      .sort()
      .join("|");
    if (key === prevPairsRef.current) return;
    prevPairsRef.current = key;

    const newEvents = collisionPairs.map((pair) => {
      const a1 = agents[pair.agent1];
      const a2 = agents[pair.agent2];
      return {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        agent1: pair.agent1,
        agent2: pair.agent2,
        risk: pair.risk,
        ttc: pair.ttc,
        decision1: a1?.decision || "?",
        decision2: a2?.decision || "?",
      };
    });

    setEvents((prev) => [...newEvents, ...prev].slice(0, MAX_EVENTS));
  }, [collisionPairs, agents]);

  useEffect(() => {
    if (scrollRef.current && !collapsed) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events, collapsed]);

  const activeCount = collisionPairs.length;

  return (
    <div
      className="rounded-xl border border-white/10 overflow-hidden"
      style={{
        background: "rgba(10,10,10,0.75)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
      }}
    >
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle
            size={14}
            className={activeCount > 0 ? "text-red-400" : "text-neutral-500"}
          />
          <span className="text-xs font-bold text-neutral-300 tracking-wider">
            RISK EVENTS
          </span>
          {activeCount > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-900/50 text-red-400">
              {activeCount} ACTIVE
            </span>
          )}
        </div>
        {collapsed ? (
          <ChevronUp size={14} className="text-neutral-500" />
        ) : (
          <ChevronDown size={14} className="text-neutral-500" />
        )}
      </button>

      {!collapsed && (
        <div
          ref={scrollRef}
          className="max-h-40 overflow-y-auto px-3 pb-3 space-y-1"
        >
          {events.length === 0 ? (
            <p className="text-neutral-600 text-xs font-mono py-2 text-center">
              No risk events recorded
            </p>
          ) : (
            events.map((ev) => (
              <div
                key={ev.id}
                className={`px-2.5 py-1.5 rounded text-[11px] font-mono flex items-center justify-between ${
                  ev.risk === "collision"
                    ? "bg-red-950/40 text-red-300 border border-red-900/30"
                    : "bg-yellow-950/30 text-yellow-300 border border-yellow-900/20"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold">
                    {ev.risk === "collision" ? "⚠" : "⚡"}
                  </span>
                  <span>
                    {ev.agent1} ↔ {ev.agent2}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px]">
                  {ev.ttc < 999 && (
                    <span className="opacity-70">TTC:{ev.ttc}s</span>
                  )}
                  <span className="opacity-50">{ev.time}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

