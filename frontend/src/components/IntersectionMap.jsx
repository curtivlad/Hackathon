import React, { useRef, useEffect } from "react";

const CANVAS_SIZE = 520;
const WORLD_SIZE = 280;
const SCALE = CANVAS_SIZE / (WORLD_SIZE * 2);
const CENTER = CANVAS_SIZE / 2;
const ROAD_W = 60 * SCALE;
const HALF_ROAD = ROAD_W / 2;

const COLORS = {
  road: "#2a2a2a",
  roadLine: "#555",
  laneDivider: "#444",
  sidewalk: "#1a1a2e",
  crosswalk: "#3a3a3a",
  vehicle_go: "#00e676",
  vehicle_yield: "#ffeb3b",
  vehicle_brake: "#ff9800",
  vehicle_stop: "#f44336",
  emergency: "#ff1744",
  risk_high: "rgba(255, 152, 0, 0.25)",
  risk_collision: "rgba(244, 67, 54, 0.35)",
  text: "#ffffff",
};

function worldToCanvas(x, y) {
  return {
    cx: CENTER + x * SCALE,
    cy: CENTER - y * SCALE,
  };
}

function drawRoad(ctx) {
  ctx.fillStyle = COLORS.sidewalk;
  ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  ctx.fillStyle = COLORS.road;
  ctx.fillRect(0, CENTER - HALF_ROAD, CANVAS_SIZE, ROAD_W);
  ctx.fillRect(CENTER - HALF_ROAD, 0, ROAD_W, CANVAS_SIZE);

  // Crosswalk strips at intersection edges
  ctx.fillStyle = COLORS.crosswalk;
  const stripW = 3, stripGap = 5, numStrips = Math.floor(ROAD_W / (stripW + stripGap));
  for (let i = 0; i < numStrips; i++) {
    const offset = CENTER - HALF_ROAD + i * (stripW + stripGap) + 2;
    ctx.fillRect(offset, CENTER - HALF_ROAD - 6, stripW, 6);
    ctx.fillRect(offset, CENTER + HALF_ROAD, stripW, 6);
    ctx.fillRect(CENTER - HALF_ROAD - 6, offset, 6, stripW);
    ctx.fillRect(CENTER + HALF_ROAD, offset, 6, stripW);
  }

  // Stop lines — full width across each road approach
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 3;
  // Top approach
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, CENTER - HALF_ROAD - 8);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - HALF_ROAD - 8);
  ctx.stroke();
  // Bottom approach
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + HALF_ROAD + 8);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER + HALF_ROAD + 8);
  ctx.stroke();
  // Right approach
  ctx.beginPath();
  ctx.moveTo(CENTER + HALF_ROAD + 8, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER + HALF_ROAD + 8, CENTER + HALF_ROAD);
  ctx.stroke();
  // Left approach
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD - 8, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER - HALF_ROAD - 8, CENTER + HALF_ROAD);
  ctx.stroke();

  // Lane dividers (dashed center lines on each road segment, outside intersection)
  ctx.setLineDash([12, 10]);
  ctx.strokeStyle = "#ffeb3b";
  ctx.lineWidth = 2;

  // Vertical road — top segment
  ctx.beginPath();
  ctx.moveTo(CENTER, 0);
  ctx.lineTo(CENTER, CENTER - HALF_ROAD);
  ctx.stroke();

  // Vertical road — bottom segment
  ctx.beginPath();
  ctx.moveTo(CENTER, CENTER + HALF_ROAD);
  ctx.lineTo(CENTER, CANVAS_SIZE);
  ctx.stroke();

  // Horizontal road — left segment
  ctx.beginPath();
  ctx.moveTo(0, CENTER);
  ctx.lineTo(CENTER - HALF_ROAD, CENTER);
  ctx.stroke();

  // Horizontal road — right segment
  ctx.beginPath();
  ctx.moveTo(CENTER + HALF_ROAD, CENTER);
  ctx.lineTo(CANVAS_SIZE, CENTER);
  ctx.stroke();

  ctx.setLineDash([]);

  // Road edge lines (solid white)
  ctx.strokeStyle = "#666";
  ctx.lineWidth = 1;

  // Vertical road edges
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, 0);
  ctx.lineTo(CENTER - HALF_ROAD, CENTER - HALF_ROAD);
  ctx.moveTo(CENTER + HALF_ROAD, 0);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - HALF_ROAD);
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + HALF_ROAD);
  ctx.lineTo(CENTER - HALF_ROAD, CANVAS_SIZE);
  ctx.moveTo(CENTER + HALF_ROAD, CENTER + HALF_ROAD);
  ctx.lineTo(CENTER + HALF_ROAD, CANVAS_SIZE);
  ctx.stroke();

  // Horizontal road edges
  ctx.beginPath();
  ctx.moveTo(0, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER - HALF_ROAD, CENTER - HALF_ROAD);
  ctx.moveTo(0, CENTER + HALF_ROAD);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER + HALF_ROAD);
  ctx.moveTo(CENTER + HALF_ROAD, CENTER - HALF_ROAD);
  ctx.lineTo(CANVAS_SIZE, CENTER - HALF_ROAD);
  ctx.moveTo(CENTER + HALF_ROAD, CENTER + HALF_ROAD);
  ctx.lineTo(CANVAS_SIZE, CENTER + HALF_ROAD);
  ctx.stroke();

  // Direction arrows on lanes
  ctx.fillStyle = "#555";
  ctx.font = "14px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const arrowOffset = HALF_ROAD / 2;
  // Vertical road: right lane = southbound ↓, left lane = northbound ↑
  ctx.fillText("↓", CENTER - arrowOffset, CENTER - HALF_ROAD - 20);
  ctx.fillText("↑", CENTER + arrowOffset, CENTER - HALF_ROAD - 20);
  ctx.fillText("↓", CENTER - arrowOffset, CENTER + HALF_ROAD + 20);
  ctx.fillText("↑", CENTER + arrowOffset, CENTER + HALF_ROAD + 20);

  // Horizontal road: top lane = westbound ←, bottom lane = eastbound →
  ctx.fillText("←", CENTER + HALF_ROAD + 20, CENTER - arrowOffset);
  ctx.fillText("→", CENTER + HALF_ROAD + 20, CENTER + arrowOffset);
  ctx.fillText("←", CENTER - HALF_ROAD - 20, CENTER - arrowOffset);
  ctx.fillText("→", CENTER - HALF_ROAD - 20, CENTER + arrowOffset);
}

function drawTrafficLights(ctx, phase) {
  const r = 6;
  const pad = 4;
  const boxW = r * 2 + pad * 2;
  const boxH = r * 2 * 2 + pad * 3;
  const offset = HALF_ROAD + 8;


  const corners = [
    // Top-left — for southbound (comes from north, lane on left side of screen)
    { x: CENTER - offset - boxW, y: CENTER - offset - boxH, green: phase === "NS_GREEN" },
    // Bottom-right — for northbound (comes from south, lane on right side of screen)
    { x: CENTER + offset, y: CENTER + offset, green: phase === "NS_GREEN" },
    // Top-right — for westbound (comes from east, lane on top of screen)
    { x: CENTER + offset, y: CENTER - offset - boxH, green: phase === "EW_GREEN" },
    // Bottom-left — for eastbound (comes from west, lane on bottom of screen)
    { x: CENTER - offset - boxW, y: CENTER + offset, green: phase === "EW_GREEN" },
  ];

  corners.forEach(({ x, y, green }) => {
    ctx.fillStyle = "#111";
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x, y, boxW, boxH, 4);
    ctx.fill();
    ctx.stroke();

    // Green light
    ctx.fillStyle = green ? "#00e676" : "#1a3a1a";
    ctx.beginPath();
    ctx.arc(x + boxW / 2, y + pad + r, r, 0, Math.PI * 2);
    ctx.fill();
    if (green) {
      ctx.shadowColor = "#00e676";
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Red light
    ctx.fillStyle = green ? "#3a1a1a" : "#f44336";
    ctx.beginPath();
    ctx.arc(x + boxW / 2, y + pad * 2 + r * 3, r, 0, Math.PI * 2);
    ctx.fill();
    if (!green) {
      ctx.shadowColor = "#f44336";
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  });
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

  if (agent.risk_level === "collision") {
    ctx.shadowColor = COLORS.emergency;
    ctx.shadowBlur = 20;
  } else if (agent.risk_level === "high") {
    ctx.shadowColor = COLORS.vehicle_brake;
    ctx.shadowBlur = 12;
  }

  const w = 10, h = 18;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((agent.direction * Math.PI) / 180);

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(-w / 2, -h / 2, w, h, 3);
  ctx.fill();

  // Windshield
  ctx.fillStyle = "rgba(255,255,255,0.15)";
  ctx.fillRect(-w / 2 + 2, -h / 2 + 2, w - 4, 5);

  // Direction arrow
  ctx.fillStyle = "rgba(0,0,0,0.4)";
  ctx.beginPath();
  ctx.moveTo(0, -h / 2 - 5);
  ctx.lineTo(-3, -h / 2);
  ctx.lineTo(3, -h / 2);
  ctx.closePath();
  ctx.fill();

  ctx.restore();
  ctx.shadowBlur = 0;

  ctx.fillStyle = COLORS.text;
  ctx.font = "bold 9px monospace";
  ctx.textAlign = "center";
  ctx.fillText(agent.agent_id, cx, cy + 18);

  ctx.fillStyle = "#aaa";
  ctx.font = "8px monospace";
  ctx.fillText(`${(agent.speed * 3.6).toFixed(0)} km/h`, cx, cy + 28);
}

function drawCollisionZone(ctx, pairs, agents) {
  for (const pair of pairs) {
    const a1 = agents[pair.agent1];
    const a2 = agents[pair.agent2];
    if (!a1 || !a2) continue;

    const p1 = worldToCanvas(a1.x, a1.y);
    const p2 = worldToCanvas(a2.x, a2.y);

    ctx.strokeStyle = pair.risk === "collision" ? "#f44336" : "#ff9800";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    ctx.moveTo(p1.cx, p1.cy);
    ctx.lineTo(p2.cx, p2.cy);
    ctx.stroke();
    ctx.setLineDash([]);

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

    for (const agent of Object.values(agents)) {
      if (agent.agent_type === "vehicle") {
        drawVehicle(ctx, agent);
      }
    }

    if (infrastructure.phase) {
      drawTrafficLights(ctx, infrastructure.phase);
    }

    // Legend
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.beginPath();
    ctx.roundRect(8, 8, 110, 75, 6);
    ctx.fill();
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
