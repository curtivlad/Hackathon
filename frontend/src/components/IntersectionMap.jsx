import React, { useRef, useEffect, useState, useCallback } from "react";

// ──────────────────────── Constants ────────────────────────
const ROAD_WIDTH = 60;
const HALF_ROAD = ROAD_WIDTH / 2;

const COLORS = {
  background: "#0d1117",
  road: "#1a1a1a",
  roadEdge: "#333",
  laneDivider: "#fcfcfc",
  building: "#151515",
  buildingEdge: "#222",
  tree: "#1c2e1f",
  vehicle_go: "#00e676",
  vehicle_yield: "#ffeb3b",
  vehicle_brake: "#ff9800",
  vehicle_stop: "#f44336",
  emergency: "#ff1744",
  drunk: "#FF69B4",
  text: "#ffffff",
};

// ──────────────────────── Camera helpers ────────────────────────
function worldToScreen(wx, wy, camera) {
  return {
    sx: (wx - camera.x) * camera.zoom + camera.canvasW / 2,
    sy: -(wy - camera.y) * camera.zoom + camera.canvasH / 2,
  };
}

function screenToWorld(sx, sy, camera) {
  return {
    wx: (sx - camera.canvasW / 2) / camera.zoom + camera.x,
    wy: -((sy - camera.canvasH / 2) / camera.zoom - camera.y),
  };
}

// ──────────────────────── Drawing functions ────────────────────────

function drawCityGrid(ctx, camera, grid) {
  const { intersections, grid_spacing } = grid;
  if (!intersections || intersections.length === 0) return;

  const margin = grid_spacing;

  ctx.fillStyle = COLORS.background;
  ctx.fillRect(0, 0, camera.canvasW, camera.canvasH);

  const xCoords = [...new Set(intersections.map(i => i.x))].sort((a, b) => a - b);
  const yCoords = [...new Set(intersections.map(i => i.y))].sort((a, b) => a - b);

  // Vertical roads
  for (const ix of xCoords) {
    const minY = Math.min(...yCoords) - margin;
    const maxY = Math.max(...yCoords) + margin;

    const left = worldToScreen(ix - HALF_ROAD, 0, camera);
    const right = worldToScreen(ix + HALF_ROAD, 0, camera);
    const top = worldToScreen(0, maxY, camera);
    const bot = worldToScreen(0, minY, camera);

    ctx.fillStyle = COLORS.road;
    ctx.fillRect(left.sx, top.sy, right.sx - left.sx, bot.sy - top.sy);

    ctx.strokeStyle = COLORS.roadEdge;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left.sx, top.sy); ctx.lineTo(left.sx, bot.sy);
    ctx.moveTo(right.sx, top.sy); ctx.lineTo(right.sx, bot.sy);
    ctx.stroke();

    const center = worldToScreen(ix, 0, camera);
    ctx.strokeStyle = COLORS.laneDivider;
    ctx.lineWidth = Math.max(1, 2 * camera.zoom);
    ctx.setLineDash([12 * camera.zoom, 12 * camera.zoom]);
    ctx.beginPath();
    ctx.moveTo(center.sx, top.sy); ctx.lineTo(center.sx, bot.sy);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Horizontal roads
  for (const iy of yCoords) {
    const minX = Math.min(...xCoords) - margin;
    const maxX = Math.max(...xCoords) + margin;

    const top = worldToScreen(0, iy + HALF_ROAD, camera);
    const bot = worldToScreen(0, iy - HALF_ROAD, camera);
    const left = worldToScreen(minX, 0, camera);
    const right = worldToScreen(maxX, 0, camera);

    ctx.fillStyle = COLORS.road;
    ctx.fillRect(left.sx, top.sy, right.sx - left.sx, bot.sy - top.sy);

    ctx.strokeStyle = COLORS.roadEdge;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left.sx, top.sy); ctx.lineTo(right.sx, top.sy);
    ctx.moveTo(left.sx, bot.sy); ctx.lineTo(right.sx, bot.sy);
    ctx.stroke();

    const center = worldToScreen(0, iy, camera);
    ctx.strokeStyle = COLORS.laneDivider;
    ctx.lineWidth = Math.max(1, 2 * camera.zoom);
    ctx.setLineDash([12 * camera.zoom, 12 * camera.zoom]);
    ctx.beginPath();
    ctx.moveTo(left.sx, center.sy); ctx.lineTo(right.sx, center.sy);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Buildings
  if (camera.zoom > 0.3) {
    drawBuildings(ctx, camera, xCoords, yCoords);
  }

  // Intersection details
  for (const inter of intersections) {
    drawIntersectionDetail(ctx, camera, inter.x, inter.y);
  }
}

function drawBuildings(ctx, camera, xCoords, yCoords) {
  const pad = 8;
  for (let i = 0; i < xCoords.length - 1; i++) {
    for (let j = 0; j < yCoords.length - 1; j++) {
      const blockLeft = xCoords[i] + HALF_ROAD + pad;
      const blockRight = xCoords[i + 1] - HALF_ROAD - pad;
      const blockBottom = yCoords[j] + HALF_ROAD + pad;
      const blockTop = yCoords[j + 1] - HALF_ROAD - pad;
      if (blockRight <= blockLeft || blockTop <= blockBottom) continue;

      const tl = worldToScreen(blockLeft, blockTop, camera);
      const br = worldToScreen(blockRight, blockBottom, camera);

      ctx.fillStyle = COLORS.building;
      ctx.strokeStyle = COLORS.buildingEdge;
      ctx.lineWidth = 1;
      ctx.fillRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);
      ctx.strokeRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);

      if (camera.zoom > 0.6) {
        const midWx = (blockLeft + blockRight) / 2;
        const midWy = (blockBottom + blockTop) / 2;
        ctx.fillStyle = COLORS.tree;
        for (const tp of [
          { x: blockLeft + 15, y: blockTop - 15 },
          { x: blockRight - 15, y: blockBottom + 15 },
          { x: midWx, y: midWy },
        ]) {
          const ts = worldToScreen(tp.x, tp.y, camera);
          const r = Math.max(3, 8 * camera.zoom);
          ctx.beginPath(); ctx.arc(ts.sx, ts.sy, r, 0, Math.PI * 2); ctx.fill();
        }
      }
    }
  }
}

function drawIntersectionDetail(ctx, camera, ix, iy) {
  const tl = worldToScreen(ix - HALF_ROAD, iy + HALF_ROAD, camera);
  const br = worldToScreen(ix + HALF_ROAD, iy - HALF_ROAD, camera);
  ctx.fillStyle = COLORS.road;
  ctx.fillRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);

  if (camera.zoom < 0.4) return;

  const cwOffset = HALF_ROAD + 4;
  const cwLen = 10;
  const roadW = ROAD_WIDTH * camera.zoom;
  const numStrips = Math.max(2, Math.floor(roadW / (8 * camera.zoom)));

  ctx.fillStyle = "rgba(224,224,224,0.4)";
  for (let s = 0; s < numStrips; s++) {
    const frac = (s + 0.5) / numStrips;
    const stripX = ix - HALF_ROAD + frac * ROAD_WIDTH;
    const stripY = iy - HALF_ROAD + frac * ROAD_WIDTH;

    // Top
    let a = worldToScreen(stripX - 1.5, iy + cwOffset + cwLen, camera);
    let b = worldToScreen(stripX + 1.5, iy + cwOffset, camera);
    ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
    // Bottom
    a = worldToScreen(stripX - 1.5, iy - cwOffset, camera);
    b = worldToScreen(stripX + 1.5, iy - cwOffset - cwLen, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    // Left
    a = worldToScreen(ix - cwOffset - cwLen, stripY - 1.5, camera);
    b = worldToScreen(ix - cwOffset, stripY + 1.5, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    // Right
    a = worldToScreen(ix + cwOffset, stripY - 1.5, camera);
    b = worldToScreen(ix + cwOffset + cwLen, stripY + 1.5, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
  }
}

function drawDemoHighlight(ctx, camera, demo) {
  if (!demo) return;
  const center = worldToScreen(demo.x, demo.y, camera);
  const r = 80 * camera.zoom;

  const grad = ctx.createRadialGradient(center.sx, center.sy, 0, center.sx, center.sy, r);
  grad.addColorStop(0, "rgba(0, 230, 118, 0.12)");
  grad.addColorStop(0.7, "rgba(0, 230, 118, 0.05)");
  grad.addColorStop(1, "rgba(0, 230, 118, 0)");
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.arc(center.sx, center.sy, r, 0, Math.PI * 2); ctx.fill();

  if (camera.zoom > 0.5) {
    ctx.fillStyle = "rgba(0, 230, 118, 0.5)";
    ctx.font = `bold ${Math.max(9, 11 * camera.zoom)}px monospace`;
    ctx.textAlign = "center";
    ctx.fillText("DEMO", center.sx, center.sy - r - 4);
  }
}

function drawTrafficLights(ctx, camera, phase, demo) {
  if (!phase || !demo) return;
  const ix = demo.x, iy = demo.y;
  const r = Math.max(3, 5 * camera.zoom);
  const pad = 2 * camera.zoom;
  const dist = HALF_ROAD + 25;

  for (const pos of [
    { wx: ix - HALF_ROAD - 8, wy: iy + dist, green: phase === "NS_GREEN" },
    { wx: ix + HALF_ROAD + 8, wy: iy - dist, green: phase === "NS_GREEN" },
    { wx: ix - dist, wy: iy + HALF_ROAD + 8, green: phase === "EW_GREEN" },
    { wx: ix + dist, wy: iy - HALF_ROAD - 8, green: phase === "EW_GREEN" },
  ]) {
    const s = worldToScreen(pos.wx, pos.wy, camera);
    const boxW = r * 2 + pad * 2, boxH = r * 4 + pad * 3;

    ctx.fillStyle = "#111"; ctx.strokeStyle = "#444"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(s.sx - boxW / 2, s.sy - boxH / 2, boxW, boxH, 3);
    ctx.fill(); ctx.stroke();

    ctx.fillStyle = pos.green ? "#00e676" : "#1a3a1a";
    ctx.beginPath(); ctx.arc(s.sx, s.sy - r - pad / 2, r, 0, Math.PI * 2); ctx.fill();
    if (pos.green) { ctx.shadowColor = "#00e676"; ctx.shadowBlur = 6; ctx.fill(); ctx.shadowBlur = 0; }

    ctx.fillStyle = pos.green ? "#3a1a1a" : "#f44336";
    ctx.beginPath(); ctx.arc(s.sx, s.sy + r + pad / 2, r, 0, Math.PI * 2); ctx.fill();
    if (!pos.green) { ctx.shadowColor = "#f44336"; ctx.shadowBlur = 6; ctx.fill(); ctx.shadowBlur = 0; }
  }
}

function drawVehicle(ctx, camera, agent) {
  const s = worldToScreen(agent.x, agent.y, camera);
  const decision = agent.decision || "go";
  let color;
  if (agent.is_drunk) color = COLORS.drunk;
  else if (agent.is_emergency) color = COLORS.emergency;
  else if (decision === "go") color = COLORS.vehicle_go;
  else if (decision === "yield") color = COLORS.vehicle_yield;
  else if (decision === "brake") color = COLORS.vehicle_brake;
  else color = COLORS.vehicle_stop;

  const isBg = agent.agent_id?.startsWith("BG_");
  const isDrunk = agent.is_drunk;

  if (isDrunk) { ctx.shadowColor = COLORS.drunk; ctx.shadowBlur = 18; }
  else if (agent.risk_level === "collision") { ctx.shadowColor = COLORS.emergency; ctx.shadowBlur = 20; }
  else if (agent.risk_level === "high") { ctx.shadowColor = COLORS.vehicle_brake; ctx.shadowBlur = 12; }

  const w = 8 * camera.zoom, h = 14 * camera.zoom;

  ctx.save();
  ctx.translate(s.sx, s.sy);
  ctx.rotate((agent.direction * Math.PI) / 180);
  ctx.globalAlpha = isBg ? 0.75 : 1.0;

  ctx.fillStyle = color;
  ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 2 * camera.zoom); ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,0.15)";
  ctx.fillRect(-w / 2 + 1.5 * camera.zoom, -h / 2 + 1.5 * camera.zoom, w - 3 * camera.zoom, 4 * camera.zoom);
  ctx.fillStyle = "rgba(0,0,0,0.4)";
  ctx.beginPath();
  ctx.moveTo(0, -h / 2 - 4 * camera.zoom);
  ctx.lineTo(-2.5 * camera.zoom, -h / 2);
  ctx.lineTo(2.5 * camera.zoom, -h / 2);
  ctx.closePath(); ctx.fill();

  ctx.globalAlpha = 1.0;
  ctx.restore();
  ctx.shadowBlur = 0;

  if (camera.zoom > 0.6) {
    if (isDrunk) {
      // Drunk driver: always show label prominently
      ctx.fillStyle = COLORS.drunk;
      ctx.font = `bold ${Math.max(9, 10 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText("🍺 DRUNK", s.sx, s.sy + h + 6 * camera.zoom);
      ctx.fillStyle = "#FF69B4";
      ctx.font = `${Math.max(7, 8 * camera.zoom)}px monospace`;
      ctx.fillText(`${(agent.speed * 3.6).toFixed(0)} km/h`, s.sx, s.sy + h + 16 * camera.zoom);
      if (agent.reason && agent.reason !== "drunk_driving") {
        ctx.fillStyle = "#ff99cc";
        ctx.font = `bold ${Math.max(6, 7 * camera.zoom)}px monospace`;
        ctx.fillText(agent.reason.toUpperCase(), s.sx, s.sy + h + 25 * camera.zoom);
      }
    } else if (!isBg) {
      ctx.fillStyle = COLORS.text;
      ctx.font = `bold ${Math.max(8, 9 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(agent.agent_id, s.sx, s.sy + h + 6 * camera.zoom);
      ctx.fillStyle = "#aaa";
      ctx.font = `${Math.max(7, 8 * camera.zoom)}px monospace`;
      ctx.fillText(`${(agent.speed * 3.6).toFixed(0)} km/h`, s.sx, s.sy + h + 16 * camera.zoom);
    } else if (camera.zoom > 0.8) {
      // BG vehicles: show ID + decision
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.font = `bold ${Math.max(7, 8 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(agent.agent_id, s.sx, s.sy + h + 6 * camera.zoom);
      if (agent.decision && agent.decision !== "go") {
        ctx.fillStyle = color;
        ctx.font = `bold ${Math.max(6, 7 * camera.zoom)}px monospace`;
        ctx.fillText(agent.decision.toUpperCase(), s.sx, s.sy + h + 15 * camera.zoom);
      }
    }
  }
}

function drawCollisionZone(ctx, camera, pairs, agents) {
  for (const pair of pairs) {
    const a1 = agents[pair.agent1], a2 = agents[pair.agent2];
    if (!a1 || !a2) continue;
    const p1 = worldToScreen(a1.x, a1.y, camera);
    const p2 = worldToScreen(a2.x, a2.y, camera);

    ctx.strokeStyle = pair.risk === "collision" ? "#f44336" : "#ff9800";
    ctx.lineWidth = 2; ctx.setLineDash([8, 6]);
    ctx.beginPath(); ctx.moveTo(p1.sx, p1.sy); ctx.lineTo(p2.sx, p2.sy); ctx.stroke();
    ctx.setLineDash([]);

    const mx = (p1.sx + p2.sx) / 2, my = (p1.sy + p2.sy) / 2;
    const radius = 28 * camera.zoom;
    const grad = ctx.createRadialGradient(mx, my, 0, mx, my, radius);
    grad.addColorStop(0, pair.risk === "collision" ? "rgba(244,67,54,0.5)" : "rgba(255,152,0,0.4)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(mx, my, radius, 0, Math.PI * 2); ctx.fill();

    if (pair.ttc < 999 && camera.zoom > 0.5) {
      ctx.fillStyle = pair.risk === "collision" ? "#f44336" : "#ff9800";
      ctx.font = `bold ${Math.max(9, 11 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(`${pair.ttc}s`, mx, my - 5);
    }
  }
}

// ──────────────────────── Main Component ────────────────────────

const DEFAULT_GRID = {
  intersections: [{ x: 0, y: 0 }],
  grid_cols: 1, grid_rows: 1, grid_spacing: 300,
  demo_intersection: { x: 0, y: 0 },
};

export default function IntersectionMap({
  agents = {}, infrastructure = {}, collisionPairs = [],
  grid = null, fullScreen = false,
  externalZoom = null, onMinZoom = null,
  trafficLightIntersections = [],
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 0.7, canvasW: 800, canvasH: 600 });
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0 });
  const gridData = grid || DEFAULT_GRID;

  // Compute min zoom so the full grid + margin fits the viewport
  const computeMinZoom = useCallback(() => {
    const g = gridData;
    if (!g.intersections || g.intersections.length < 2) return 0.15;
    const xs = g.intersections.map(i => i.x);
    const ys = g.intersections.map(i => i.y);
    const worldW = (Math.max(...xs) - Math.min(...xs)) + g.grid_spacing * 1.2;
    const worldH = (Math.max(...ys) - Math.min(...ys)) + g.grid_spacing * 1.2;
    const zx = camera.canvasW / worldW;
    const zy = camera.canvasH / worldH;
    return Math.max(0.1, Math.min(zx, zy));
  }, [gridData, camera.canvasW, camera.canvasH]);

  // Sync external zoom from slider, clamped to minZoom
  useEffect(() => {
    if (externalZoom !== null && externalZoom !== undefined) {
      const minZ = computeMinZoom();
      setCamera(prev => ({ ...prev, zoom: Math.max(minZ, externalZoom) }));
    }
  }, [externalZoom, computeMinZoom]);

  // Report minZoom to parent so slider can be clamped
  useEffect(() => {
    if (onMinZoom) onMinZoom(computeMinZoom());
  }, [computeMinZoom, onMinZoom]);

  useEffect(() => {
    const updateSize = () => {
      const c = containerRef.current;
      if (!c) return;
      setCamera(prev => ({ ...prev, canvasW: c.clientWidth, canvasH: c.clientHeight }));
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // No wheel zoom — use slider instead.
  // But prevent page from scrolling when hovering over canvas.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const prevent = (e) => e.preventDefault();
    canvas.addEventListener("wheel", prevent, { passive: false });
    return () => canvas.removeEventListener("wheel", prevent);
  }, []);

  const handleMouseDown = useCallback((e) => {
    if (e.button !== 0) return;
    dragRef.current = { dragging: true, lastX: e.clientX, lastY: e.clientY };
  }, []);

  const handleMouseMove = useCallback((e) => {
    if (!dragRef.current.dragging) return;
    const dx = e.clientX - dragRef.current.lastX, dy = e.clientY - dragRef.current.lastY;
    dragRef.current.lastX = e.clientX; dragRef.current.lastY = e.clientY;
    setCamera(prev => ({ ...prev, x: prev.x - dx / prev.zoom, y: prev.y + dy / prev.zoom }));
  }, []);

  const handleMouseUp = useCallback(() => { dragRef.current.dragging = false; }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const cam = { ...camera };

    // HiDPI: set canvas buffer size to dpr * CSS size
    canvas.width = cam.canvasW * dpr;
    canvas.height = cam.canvasH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, cam.canvasW, cam.canvasH);
    drawCityGrid(ctx, cam, gridData);
    drawDemoHighlight(ctx, cam, gridData.demo_intersection);
    drawCollisionZone(ctx, cam, collisionPairs, agents);

    const bgV = [], demoV = [], drunkV = [];
    for (const a of Object.values(agents)) {
      if (a.agent_type !== "vehicle") continue;
      if (a.is_drunk) drunkV.push(a);
      else if (a.agent_id?.startsWith("BG_")) bgV.push(a);
      else demoV.push(a);
    }
    for (const v of bgV) drawVehicle(ctx, cam, v);
    for (const v of demoV) drawVehicle(ctx, cam, v);
    for (const v of drunkV) drawVehicle(ctx, cam, v);

    if (infrastructure?.phase) drawTrafficLights(ctx, cam, infrastructure.phase, gridData.demo_intersection);

    // Draw traffic lights at semaforizate intersections
    if (trafficLightIntersections && trafficLightIntersections.length > 0) {
      for (const tli of trafficLightIntersections) {
        // Skip the demo intersection if it already has lights from infrastructure
        if (infrastructure?.phase && gridData.demo_intersection &&
            tli.x === gridData.demo_intersection.x && tli.y === gridData.demo_intersection.y) continue;
        drawTrafficLights(ctx, cam, tli.phase, tli);
      }
    }

    ctx.fillStyle = "rgba(255,255,255,0.2)";
    ctx.font = "11px monospace"; ctx.textAlign = "right";
    ctx.fillText(`Zoom: ${(cam.zoom * 100).toFixed(0)}%`, cam.canvasW - 12, cam.canvasH - 12);
  }, [agents, infrastructure, collisionPairs, camera, gridData]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%", height: "100%",
        position: fullScreen ? "fixed" : "relative",
        inset: fullScreen ? 0 : undefined,
        zIndex: fullScreen ? 0 : undefined,
        cursor: dragRef.current?.dragging ? "grabbing" : "grab",
        overflow: "hidden",
      }}
    >
      <canvas
        ref={canvasRef}
        width={camera.canvasW} height={camera.canvasH}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}
