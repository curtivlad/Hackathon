import React, { useRef, useEffect } from "react";

const CANVAS_SIZE = 500;
const WORLD_SIZE = 280;   // metri vizibili pe fiecare directie
const SCALE = CANVAS_SIZE / (WORLD_SIZE * 2);
const CENTER = CANVAS_SIZE / 2;

// Culori
const COLORS = {
  road: "#2a2a2a",
  roadLine: "#555",
  sidewalk: "#1a1a2e",
  vehicle_go: "#00e676",
  vehicle_yield: "#ffeb3b",
  vehicle_brake: "#ff9800",
  vehicle_stop: "#f44336",
  emergency: "#ff1744",
  infrastructure: "#2196f3",
  risk_high: "rgba(255, 152, 0, 0.25)",
  risk_collision: "rgba(244, 67, 54, 0.35)",
  text: "#ffffff",
  grid: "#333",
};

function worldToCanvas(x, y) {
  return {
    cx: CENTER + x * SCALE,
    cy: CENTER - y * SCALE,   // Y inversat (sus = pozitiv)
  };
}

function drawRoad(ctx) {
  // Fundal
  ctx.fillStyle = COLORS.sidewalk;
  ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  const roadW = 60 * SCALE;
  const half = roadW / 2;

  // Drum orizontal
  ctx.fillStyle = COLORS.road;
  ctx.fillRect(0, CENTER - half, CANVAS_SIZE, roadW);

  // Drum vertical
  ctx.fillRect(CENTER - half, 0, roadW, CANVAS_SIZE);

  // Linii mediane
  ctx.setLineDash([20, 15]);
  ctx.strokeStyle = COLORS.roadLine;
  ctx.lineWidth = 2;

  ctx.beginPath();
  ctx.moveTo(0, CENTER);
  ctx.lineTo(CANVAS_SIZE, CENTER);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(CENTER, 0);
  ctx.lineTo(CENTER, CANVAS_SIZE);
  ctx.stroke();

  ctx.setLineDash([]);
}

function drawTrafficLight(ctx, phase) {
  const size = 18;
  const x = CENTER + 38;
  const y = CENTER - 38;

  ctx.fillStyle = "#222";
  ctx.fillRect(x - 2, y - 2, size + 4, size * 2 + 4 + 6);

  // NS light
  ctx.fillStyle = phase === "NS_GREEN" ? "#00e676" : "#f44336";
  ctx.beginPath();
  ctx.arc(x + size / 2, y + size / 2, size / 2 - 1, 0, Math.PI * 2);
  ctx.fill();

  // EW light
  ctx.fillStyle = phase === "EW_GREEN" ? "#00e676" : "#f44336";
  ctx.beginPath();
  ctx.arc(x + size / 2, y + size + 6 + size / 2, size / 2 - 1, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#aaa";
  ctx.font = "9px monospace";
  ctx.fillText("NS", x + size + 3, y + size / 2 + 4);
  ctx.fillText("EW", x + size + 3, y + size + 6 + size / 2 + 4);
}

function drawVehicle(ctx, agent) {
  const { cx, cy } = worldToCanvas(agent.x, agent.y);

  const decision = agent.decision || "go";
  let color;
  if (agent.is_emergency) color = COLORS.emergency;
  else if (decision === "go") color = COLORS.vehicle_go;
  else if (decision === "yield") color = COLORS.vehicle_yield;
  else if (decision === "brake") color = COLORS.vehicle_brake;
  else color = COLORS.vehicle_stop;

  // Puls (glow)
  if (agent.risk_level === "collision") {
    ctx.shadowColor = COLORS.emergency;
    ctx.shadowBlur = 20;
  } else if (agent.risk_level === "high") {
    ctx.shadowColor = COLORS.vehicle_brake;
    ctx.shadowBlur = 12;
  }

  // Corpul vehiculului
  const w = 12, h = 20;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((agent.direction * Math.PI) / 180);

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(-w / 2, -h / 2, w, h, 3);
  ctx.fill();

  // Sageata de directie
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.beginPath();
  ctx.moveTo(0, -h / 2 - 6);
  ctx.lineTo(-4, -h / 2);
  ctx.lineTo(4, -h / 2);
  ctx.closePath();
  ctx.fill();

  ctx.restore();
  ctx.shadowBlur = 0;

  // Label
  ctx.fillStyle = COLORS.text;
  ctx.font = "bold 10px monospace";
  ctx.textAlign = "center";
  ctx.fillText(agent.agent_id, cx, cy + 22);

  // Viteza
  ctx.fillStyle = "#aaa";
  ctx.font = "9px monospace";
  ctx.fillText(`${(agent.speed * 3.6).toFixed(0)} km/h`, cx, cy + 33);
}

function drawCollisionZone(ctx, pairs, agents) {
  for (const pair of pairs) {
    const a1 = agents[pair.agent1];
    const a2 = agents[pair.agent2];
    if (!a1 || !a2) continue;

    const p1 = worldToCanvas(a1.x, a1.y);
    const p2 = worldToCanvas(a2.x, a2.y);

    // Linie intre cei doi
    ctx.strokeStyle = pair.risk === "collision" ? "#f44336" : "#ff9800";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    ctx.moveTo(p1.cx, p1.cy);
    ctx.lineTo(p2.cx, p2.cy);
    ctx.stroke();
    ctx.setLineDash([]);

    // Zona de pericol la mijloc
    const mx = (p1.cx + p2.cx) / 2;
    const my = (p1.cy + p2.cy) / 2;
    const radius = 28;

    const grad = ctx.createRadialGradient(mx, my, 0, mx, my, radius);
    grad.addColorStop(0, pair.risk === "collision" ? "rgba(244,67,54,0.5)" : "rgba(255,152,0,0.4)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(mx, my, radius, 0, Math.PI * 2);
    ctx.fill();

    // TTC label
    if (pair.ttc < 999) {
      ctx.fillStyle = pair.risk === "collision" ? "#f44336" : "#ff9800";
      ctx.font = "bold 11px monospace";
      ctx.textAlign = "center";
      ctx.fillText(`⚠ ${pair.ttc}s`, mx, my - 5);
    }
  }
}

export default function IntersectionMap({ agents = {}, infrastructure = {}, collisionPairs = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    drawRoad(ctx);
    drawCollisionZone(ctx, collisionPairs, agents);

    // Deseneaza vehiculele
    for (const agent of Object.values(agents)) {
      if (agent.agent_type === "vehicle") {
        drawVehicle(ctx, agent);
      }
    }

    // Semafor
    if (infrastructure.phase) {
      drawTrafficLight(ctx, infrastructure.phase);
    }

    // Legenda
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(8, 8, 120, 75);
    ctx.font = "9px monospace";
    const legend = [
      [COLORS.vehicle_go, "GO"],
      [COLORS.vehicle_yield, "YIELD"],
      [COLORS.vehicle_brake, "BRAKE"],
      [COLORS.vehicle_stop, "STOP"],
      [COLORS.emergency, "EMERGENCY"],
    ];
    legend.forEach(([color, label], i) => {
      ctx.fillStyle = color;
      ctx.fillRect(14, 16 + i * 13, 10, 9);
      ctx.fillStyle = "#ddd";
      ctx.fillText(label, 30, 25 + i * 13);
    });

  }, [agents, infrastructure, collisionPairs]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_SIZE}
      height={CANVAS_SIZE}
      style={{ borderRadius: "12px", border: "1px solid #333" }}
    />
  );
}
