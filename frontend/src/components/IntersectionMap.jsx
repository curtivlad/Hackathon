import React, { useRef, useEffect } from "react";

const CANVAS_SIZE = 520;
const WORLD_SIZE = 280;
const SCALE = CANVAS_SIZE / (WORLD_SIZE * 2);
const CENTER = CANVAS_SIZE / 2;
const ROAD_W = 60 * SCALE;
const HALF_ROAD = ROAD_W / 2;

const COLORS = {
  road: "#222222",
  roadLine: "#555",
  laneDivider: "#444",
  sidewalk: "#111111",
  crosswalk: "#e0e0e0",
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

  ctx.fillStyle = COLORS.crosswalk;
  const stripW = 4, stripGap = 8;
  const numStrips = Math.floor((ROAD_W + stripGap) / (stripW + stripGap));
  const totalStripsWidth = numStrips * stripW + (numStrips - 1) * stripGap;
  const sideMargin = (ROAD_W - totalStripsWidth) / 2;

  const cwStart = HALF_ROAD + 2;      // Inner bounding line
  const cwPadding = 4;                // Gap between bounding lines and zebra
  const cwZebraStart = cwStart + cwPadding;
  const cwZebraLength = 12;           // Length of the zebra strips
  const cwOuterLine = cwZebraStart + cwZebraLength + cwPadding; // Outer bounding line

  // Draw zebra stripes
  for (let i = 0; i < numStrips; i++) {
    const offset = CENTER - HALF_ROAD + sideMargin + i * (stripW + stripGap);
    // Top
    ctx.fillRect(offset, CENTER - cwZebraStart - cwZebraLength, stripW, cwZebraLength);
    // Bottom
    ctx.fillRect(offset, CENTER + cwZebraStart, stripW, cwZebraLength);
    // Left
    ctx.fillRect(CENTER - cwZebraStart - cwZebraLength, offset, cwZebraLength, stripW);
    // Right
    ctx.fillRect(CENTER + cwZebraStart, offset, cwZebraLength, stripW);
  }

  // Stop lines — lines bounding the crosswalks (before and after)
  ctx.strokeStyle = COLORS.crosswalk;
  ctx.lineWidth = 2;
  
  // Top crosswalk lines
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, CENTER - cwOuterLine); // outer line
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - cwOuterLine);
  ctx.moveTo(CENTER - HALF_ROAD, CENTER - cwStart);     // inner line (stop line)
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - cwStart);
  ctx.stroke();
  
  // Bottom crosswalk lines
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + cwStart);     // inner line (stop line)
  ctx.lineTo(CENTER + HALF_ROAD, CENTER + cwStart);
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + cwOuterLine); // outer line
  ctx.lineTo(CENTER + HALF_ROAD, CENTER + cwOuterLine);
  ctx.stroke();
  
  // Left crosswalk lines
  ctx.beginPath();
  ctx.moveTo(CENTER - cwOuterLine, CENTER - HALF_ROAD); // outer line
  ctx.lineTo(CENTER - cwOuterLine, CENTER + HALF_ROAD);
  ctx.moveTo(CENTER - cwStart, CENTER - HALF_ROAD);     // inner line (stop line)
  ctx.lineTo(CENTER - cwStart, CENTER + HALF_ROAD);
  ctx.stroke();
  
  // Right crosswalk lines
  ctx.beginPath();
  ctx.moveTo(CENTER + cwStart, CENTER - HALF_ROAD);     // inner line (stop line)
  ctx.lineTo(CENTER + cwStart, CENTER + HALF_ROAD);
  ctx.moveTo(CENTER + cwOuterLine, CENTER - HALF_ROAD); // outer line
  ctx.lineTo(CENTER + cwOuterLine, CENTER + HALF_ROAD);
  ctx.stroke();

  // Lane dividers (dashed lines separating opposite directions)
  ctx.setLineDash([20, 20]);
  ctx.strokeStyle = "#fcfcfc"; // lighter color towards white
  ctx.lineWidth = 3;

  const dashEnd = cwOuterLine + 8; // start dashed line slightly further from crosswalk

  // Vertical road — top segment (Draw from dashEnd outwards so the gap near intersection is full)
  ctx.beginPath();
  ctx.moveTo(CENTER, CENTER - dashEnd);
  ctx.lineTo(CENTER, 0);
  ctx.stroke();

  // Vertical road — bottom segment
  ctx.beginPath();
  ctx.moveTo(CENTER, CENTER + dashEnd);
  ctx.lineTo(CENTER, CANVAS_SIZE);
  ctx.stroke();

  // Horizontal road — left segment (Draw from dashEnd outwards)
  ctx.beginPath();
  ctx.moveTo(CENTER - dashEnd, CENTER);
  ctx.lineTo(0, CENTER);
  ctx.stroke();

  // Horizontal road — right segment
  ctx.beginPath();
  ctx.moveTo(CENTER + dashEnd, CENTER);
  ctx.lineTo(CANVAS_SIZE, CENTER);
  ctx.stroke();

  ctx.setLineDash([]);

  
  ctx.strokeStyle = "#666";
  ctx.lineWidth = 1;

  
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, 0);
  ctx.lineTo(CENTER - HALF_ROAD, CENTER - dashEnd + 8);
  ctx.moveTo(CENTER + HALF_ROAD, 0);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - dashEnd + 8);
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + dashEnd - 8);
  ctx.lineTo(CENTER - HALF_ROAD, CANVAS_SIZE);
  ctx.moveTo(CENTER + HALF_ROAD, CENTER + dashEnd - 8);
  ctx.lineTo(CENTER + HALF_ROAD, CANVAS_SIZE);
  ctx.stroke();

  
  ctx.beginPath();
  ctx.moveTo(0, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER - dashEnd + 8, CENTER - HALF_ROAD);
  ctx.moveTo(0, CENTER + HALF_ROAD);
  ctx.lineTo(CENTER - dashEnd + 8, CENTER + HALF_ROAD);
  ctx.moveTo(CENTER + dashEnd - 8, CENTER - HALF_ROAD);
  ctx.lineTo(CANVAS_SIZE, CENTER - HALF_ROAD);
  ctx.moveTo(CENTER + dashEnd - 8, CENTER + HALF_ROAD);
  ctx.lineTo(CANVAS_SIZE, CENTER + HALF_ROAD);
  ctx.stroke();

  
  // Directional Arrows on the lanes (Only on approaching lanes like in real life)
  ctx.fillStyle = "#ffffff"; 
  const arrowOffset = HALF_ROAD / 2;
  const arrowDist = HALF_ROAD + 40;

  // Helper function to draw a united straight+right arrow (shrunken & proportioned like photo)
  const drawComplexArrow = (x, y, rotation) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rotation);
    // Scales down the entire arrow and slightly squishes it horizontally for that "painted on road" perspective
    ctx.scale(0.35, 0.45); 

    ctx.beginPath();
    
    // Main Straight Shaft (Thicker and shorter)
    ctx.moveTo(-4, 25);
    ctx.lineTo(4, 25);
    ctx.lineTo(4, 3); // Go up right side of shaft
    
    // Branch off to the right turn
    ctx.lineTo(15, -6); // Outer right branch line
    ctx.lineTo(13, -11); // Inner right branch
    ctx.lineTo(26, -9); // Point of right arrow head
    ctx.lineTo(24, 7);  // Bottom tail of right arrow head
    ctx.lineTo(18, 0); // Inner recess of right arrow head
    ctx.lineTo(6, 12);  // Come back to straight arrow shaft
    
    // Back to straight arrow head
    ctx.lineTo(4, -12);  // Up to right base of straight arrow head
    ctx.lineTo(12, -12); // Right wing extension
    ctx.lineTo(0, -32);  // TOP TIP (Sharp top)
    ctx.lineTo(-12, -12);// Left wing extension
    ctx.lineTo(-4, -12); // Left base of straight arrow head
    
    // Down completely straight down the left side
    ctx.lineTo(-4, 25); 
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  };

  // Top approach (driving DOWN) => Left side, rotation 180deg (Math.PI)
  drawComplexArrow(CENTER - arrowOffset, CENTER - arrowDist, Math.PI);

  // Bottom approach (driving UP) => Right side, rotation 0deg
  drawComplexArrow(CENTER + arrowOffset, CENTER + arrowDist, 0);

  // Left approach (driving RIGHT) => Bottom side, rotation 90deg (Math.PI/2)
  drawComplexArrow(CENTER - arrowDist, CENTER + arrowOffset, Math.PI / 2);

  // Right approach (driving LEFT) => Top side, rotation 270deg (-Math.PI/2)
  drawComplexArrow(CENTER + arrowDist, CENTER - arrowOffset, -Math.PI / 2);
}

function drawDecorations(ctx) {
  // Draw dotted guidelines (very faint) in the intersection to show lanes connecting
  ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 6]);

  // NS Guidelines
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD / 2, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER - HALF_ROAD / 2, CENTER + HALF_ROAD);
  ctx.moveTo(CENTER + HALF_ROAD / 2, CENTER - HALF_ROAD);
  ctx.lineTo(CENTER + HALF_ROAD / 2, CENTER + HALF_ROAD);
  ctx.stroke();

  // EW Guidelines
  ctx.beginPath();
  ctx.moveTo(CENTER - HALF_ROAD, CENTER - HALF_ROAD / 2);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER - HALF_ROAD / 2);
  ctx.moveTo(CENTER - HALF_ROAD, CENTER + HALF_ROAD / 2);
  ctx.lineTo(CENTER + HALF_ROAD, CENTER + HALF_ROAD / 2);
  ctx.stroke();

  // Draw some basic background elements like grass/building blocks
  const blockSize = Math.min(CANVAS_SIZE / 2 - HALF_ROAD, CANVAS_SIZE / 2 - HALF_ROAD);
  
  // Create a pattern for grass/concrete
  ctx.fillStyle = "#151515"; // slightly lighter than pure sidewalk
  ctx.setLineDash([]);
  
  // Top Left block
  ctx.fillRect(10, 10, CENTER - HALF_ROAD - 20, CENTER - HALF_ROAD - 20);
  // Top Right block
  ctx.fillRect(CENTER + HALF_ROAD + 10, 10, CENTER - HALF_ROAD - 20, CENTER - HALF_ROAD - 20);
  // Bottom Left block
  ctx.fillRect(10, CENTER + HALF_ROAD + 10, CENTER - HALF_ROAD - 20, CENTER - HALF_ROAD - 20);
  // Bottom Right block
  ctx.fillRect(CENTER + HALF_ROAD + 10, CENTER + HALF_ROAD + 10, CENTER - HALF_ROAD - 20, CENTER - HALF_ROAD - 20);

  // Add some trees / bushes (circles)
  ctx.fillStyle = "#1c2e1f"; // Dark green
  ctx.beginPath(); ctx.arc(40, 40, 12, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(80, 50, 16, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(CANVAS_SIZE - 40, 60, 14, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(50, CANVAS_SIZE - 50, 18, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(CANVAS_SIZE - 70, CANVAS_SIZE - 40, 15, 0, Math.PI * 2); ctx.fill();
}

function drawTrafficLights(ctx, phase) {
  const r = 6;
  const pad = 4;
  const boxW = r * 2 + pad * 2;
  const boxH = r * 2 * 2 + pad * 3;
  const cwPaddingOuter = HALF_ROAD + 14 + 14 + 2; // Position strictly behind crosswalk
  const rightLaneOffset = HALF_ROAD + 8; // Offset to sit next to the lane

  // Put traffic lights ON the corner right before entering the intersection
  // Each structure is responsible for the lane PRECEDING the intersection
  const corners = [
    // Top approach (facing north cars) => sits on the left side (or above) the Top road crosswalk
    { x: CENTER - HALF_ROAD - boxW - 5, y: CENTER - cwPaddingOuter - boxH, green: phase === "NS_GREEN" },
    
    // Bottom approach (facing south cars) => sits on the right side of the Bottom road crosswalk
    { x: CENTER + HALF_ROAD + 5, y: CENTER + cwPaddingOuter, green: phase === "NS_GREEN" },
    
    // Left approach (facing east cars) => sits on bottom side of the Left road crosswalk
    { x: CENTER - cwPaddingOuter - boxH, y: CENTER + HALF_ROAD + 5, green: phase === "EW_GREEN", rotate: true },
    
    // Right approach (facing west cars) => sits on top side of the Right road crosswalk
    { x: CENTER + cwPaddingOuter, y: CENTER - HALF_ROAD - boxW - 5, green: phase === "EW_GREEN", rotate: true },
  ];

  corners.forEach(({ x, y, green, rotate }) => {
    ctx.save();
    ctx.translate(x, y);

    if (rotate) {
      // Rotate 90 degrees for EW lights so they go horizontally
      ctx.translate(boxH/2, boxW/2);
      ctx.rotate(-Math.PI / 2);
      ctx.translate(-boxW/2, -boxH/2);
      // Ensure drawing happens at 0,0 locally
      x = 0; y = 0;
    } else {
      x = 0; y = 0; 
    }

    ctx.fillStyle = "#111";
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x, y, boxW, boxH, 4);
    ctx.fill();
    ctx.stroke();

    
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

    ctx.restore(); // MUST RESTORE CONTEXT AFTER ROTATING IT
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

  
  ctx.fillStyle = "rgba(255,255,255,0.15)";
  ctx.fillRect(-w / 2 + 2, -h / 2 + 2, w - 4, 5);

  
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
      ctx.fillText(`${pair.ttc}s`, mx, my - 5);
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
    
    // Draw background decorations first
    drawDecorations(ctx);
    
    // Draw road overlay
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

  }, [agents, infrastructure, collisionPairs]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_SIZE}
      height={CANVAS_SIZE}
      className="rounded-xl border border-neutral-800"
    />
  );
}
