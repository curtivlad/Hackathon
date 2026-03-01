import React, { useRef, useEffect, useState, useCallback } from "react";

const ROAD_WIDTH = 60;
const HALF_ROAD = ROAD_WIDTH / 2;

const COLORS = {
  background: "#101010",
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
  police: "#4488ff",
  drunk: "#FF69B4",
  text: "#ffffff",
};

const BUILDING_IMAGE_SRCS = [
  "/unnamed.jpg",
  "/unnamed2.jpg",
  "/unnamed3.jpg",
  "/unnamed4.jpg",
  "/unnamed5.jpg",
];
const _buildingImages = BUILDING_IMAGE_SRCS.map((src) => {
  const img = new Image();
  img.src = src;
  return img;
});
let _buildingImagesLoaded = false;
let _buildingImagesLoadCount = 0;
_buildingImages.forEach((img) => {
  img.onload = () => {
    _buildingImagesLoadCount++;
    if (_buildingImagesLoadCount === _buildingImages.length) _buildingImagesLoaded = true;
  };
});

function _seededRandom(seed) {
  let s = Math.abs(seed) || 1;
  return function () {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

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

function drawCityGrid(ctx, camera, grid) {
  const { intersections, grid_spacing } = grid;
  if (!intersections || intersections.length === 0) return;

  ctx.fillStyle = COLORS.background;
  ctx.fillRect(0, 0, camera.canvasW, camera.canvasH);

  const xCoords = [...new Set(intersections.map(i => i.x))].sort((a, b) => a - b);
  const yCoords = [...new Set(intersections.map(i => i.y))].sort((a, b) => a - b);

  const minX = Math.min(...xCoords);
  const maxX = Math.max(...xCoords);
  const minY = Math.min(...yCoords);
  const maxY = Math.max(...yCoords);

  const isSingleIntersection = xCoords.length === 1 && yCoords.length === 1;
  const roadExtend = isSingleIntersection ? (grid_spacing || 200) * 0.65 : 0;
  const roadMinX = minX - roadExtend;
  const roadMaxX = maxX + roadExtend;
  const roadMinY = minY - roadExtend;
  const roadMaxY = maxY + roadExtend;

  const mapMargin = 12;
  const borderRadius = 18 * camera.zoom;
  const mapTL = worldToScreen(roadMinX - HALF_ROAD, roadMaxY + HALF_ROAD, camera);
  const mapBR = worldToScreen(roadMaxX + HALF_ROAD, roadMinY - HALF_ROAD, camera);
  const mapX = mapTL.sx - mapMargin;
  const mapY = mapTL.sy - mapMargin;
  const mapW = mapBR.sx - mapTL.sx + mapMargin * 2;
  const mapH = mapBR.sy - mapTL.sy + mapMargin * 2;
  const clampedRadius = Math.min(borderRadius, mapW / 2, mapH / 2);

  ctx.save();
  ctx.beginPath();
  ctx.roundRect(mapTL.sx, mapTL.sy, mapBR.sx - mapTL.sx, mapBR.sy - mapTL.sy, clampedRadius);
  ctx.clip();

  const cwClear = HALF_ROAD + 8 + 10 + 2 + 0.6 + 4;

  function drawSegmentedDashes(ctx, camera, fixedCoord, isVertical, roadStart, roadEnd, crossings) {
    const zones = crossings.map(c => ({ lo: c - cwClear, hi: c + cwClear }));
    zones.sort((a, b) => a.lo - b.lo);

    const segments = [];
    let cursor = roadStart;
    for (const z of zones) {
      if (z.lo > cursor) segments.push({ start: cursor, end: z.lo });
      cursor = Math.max(cursor, z.hi);
    }
    if (cursor < roadEnd) segments.push({ start: cursor, end: roadEnd });

    const dashUnit = 6;
    for (const seg of segments) {
      const len = seg.end - seg.start;
      if (len < 2) continue;
      const numDashes = Math.max(1, Math.round(len / (dashUnit * 2)));
      const actualDash = (len / numDashes) / 2;
      const pxDash = actualDash * camera.zoom;
      ctx.setLineDash([pxDash, pxDash]);

      if (isVertical) {
        const a = worldToScreen(fixedCoord, seg.end, camera);
        const b = worldToScreen(fixedCoord, seg.start, camera);
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
      } else {
        const a = worldToScreen(seg.start, fixedCoord, camera);
        const b = worldToScreen(seg.end, fixedCoord, camera);
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);
  }

  for (const ix of xCoords) {
    const left = worldToScreen(ix - HALF_ROAD, 0, camera);
    const right = worldToScreen(ix + HALF_ROAD, 0, camera);
    const top = worldToScreen(0, roadMaxY + HALF_ROAD, camera);
    const bot = worldToScreen(0, roadMinY - HALF_ROAD, camera);

    ctx.fillStyle = COLORS.road;
    ctx.fillRect(left.sx, top.sy, right.sx - left.sx, bot.sy - top.sy);

    ctx.strokeStyle = COLORS.roadEdge;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left.sx, top.sy); ctx.lineTo(left.sx, bot.sy);
    ctx.moveTo(right.sx, top.sy); ctx.lineTo(right.sx, bot.sy);
    ctx.stroke();

    ctx.strokeStyle = COLORS.laneDivider;
    ctx.lineWidth = Math.max(1, 2 * camera.zoom);
    drawSegmentedDashes(ctx, camera, ix, true, roadMinY - HALF_ROAD, roadMaxY + HALF_ROAD, yCoords);
  }

  for (const iy of yCoords) {
    const top = worldToScreen(0, iy + HALF_ROAD, camera);
    const bot = worldToScreen(0, iy - HALF_ROAD, camera);
    const left = worldToScreen(roadMinX - HALF_ROAD, 0, camera);
    const right = worldToScreen(roadMaxX + HALF_ROAD, 0, camera);

    ctx.fillStyle = COLORS.road;
    ctx.fillRect(left.sx, top.sy, right.sx - left.sx, bot.sy - top.sy);

    ctx.strokeStyle = COLORS.roadEdge;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left.sx, top.sy); ctx.lineTo(right.sx, top.sy);
    ctx.moveTo(left.sx, bot.sy); ctx.lineTo(right.sx, bot.sy);
    ctx.stroke();

    ctx.strokeStyle = COLORS.laneDivider;
    ctx.lineWidth = Math.max(1, 2 * camera.zoom);
    drawSegmentedDashes(ctx, camera, iy, false, roadMinX - HALF_ROAD, roadMaxX + HALF_ROAD, xCoords);
  }

  ctx.fillStyle = COLORS.road;
  for (const c of [
    { x: minX, y: maxY }, { x: maxX, y: maxY },
    { x: maxX, y: minY }, { x: minX, y: minY },
  ]) {
    const tl = worldToScreen(c.x - HALF_ROAD, c.y + HALF_ROAD, camera);
    const br = worldToScreen(c.x + HALF_ROAD, c.y - HALF_ROAD, camera);
    ctx.fillRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);
  }

  if (camera.zoom > 0.3) {
    if (isSingleIntersection) {
      drawSingleIntersectionSidewalks(ctx, camera, xCoords[0], yCoords[0], roadExtend);
    } else {
      drawBuildings(ctx, camera, xCoords, yCoords);
    }
  }

  const bounds = { minX, maxX, minY, maxY };
  for (const inter of intersections) {
    drawIntersectionDetail(ctx, camera, inter.x, inter.y, bounds);
  }

  ctx.restore();

  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(mapX, mapY, mapW, mapH, clampedRadius + mapMargin * 0.3);
  ctx.stroke();
}

function drawSingleIntersectionSidewalks(ctx, camera, cx, cy, extend) {
  const pad = 8;
  const sidewalkColor = "#2a2a2a";
  const sidewalkEdge = "#3a3a3a";
  const curbColor = "#444";

  const quadrants = [
    { left: cx + HALF_ROAD, right: cx + extend + HALF_ROAD, bottom: cy + HALF_ROAD, top: cy + extend + HALF_ROAD },
    { left: cx - extend - HALF_ROAD, right: cx - HALF_ROAD, bottom: cy + HALF_ROAD, top: cy + extend + HALF_ROAD },
    { left: cx + HALF_ROAD, right: cx + extend + HALF_ROAD, bottom: cy - extend - HALF_ROAD, top: cy - HALF_ROAD },
    { left: cx - extend - HALF_ROAD, right: cx - HALF_ROAD, bottom: cy - extend - HALF_ROAD, top: cy - HALF_ROAD },
  ];

  for (const q of quadrants) {
    const tl = worldToScreen(q.left, q.top, camera);
    const br = worldToScreen(q.right, q.bottom, camera);
    const w = br.sx - tl.sx;
    const h = br.sy - tl.sy;

    ctx.fillStyle = sidewalkColor;
    ctx.fillRect(tl.sx, tl.sy, w, h);

    ctx.strokeStyle = sidewalkEdge;
    ctx.lineWidth = 1;
    ctx.strokeRect(tl.sx, tl.sy, w, h);

    if (camera.zoom > 0.5) {
      const padPx = pad * camera.zoom;
      ctx.strokeStyle = curbColor;
      ctx.lineWidth = Math.max(1, 1.5 * camera.zoom);
      ctx.beginPath();
      ctx.moveTo(tl.sx + padPx, tl.sy);
      ctx.lineTo(tl.sx + padPx, tl.sy + h);
      ctx.moveTo(br.sx - padPx, tl.sy);
      ctx.lineTo(br.sx - padPx, tl.sy + h);
      ctx.moveTo(tl.sx, tl.sy + padPx);
      ctx.lineTo(tl.sx + w, tl.sy + padPx);
      ctx.moveTo(tl.sx, br.sy - padPx);
      ctx.lineTo(tl.sx + w, br.sy - padPx);
      ctx.stroke();

      const tileSize = 8 * camera.zoom;
      if (tileSize > 3) {
        ctx.strokeStyle = "rgba(255,255,255,0.04)";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        for (let tx = tl.sx; tx < tl.sx + padPx; tx += tileSize) {
          ctx.moveTo(tx, tl.sy);
          ctx.lineTo(tx, tl.sy + h);
        }
        for (let ty = tl.sy; ty < tl.sy + h; ty += tileSize) {
          ctx.moveTo(tl.sx, ty);
          ctx.lineTo(tl.sx + padPx, ty);
        }
        for (let tx = br.sx - padPx; tx < br.sx; tx += tileSize) {
          ctx.moveTo(tx, tl.sy);
          ctx.lineTo(tx, tl.sy + h);
        }
        for (let ty = tl.sy; ty < tl.sy + h; ty += tileSize) {
          ctx.moveTo(br.sx - padPx, ty);
          ctx.lineTo(br.sx, ty);
        }
        for (let tx = tl.sx + padPx; tx < br.sx - padPx; tx += tileSize) {
          ctx.moveTo(tx, tl.sy);
          ctx.lineTo(tx, tl.sy + padPx);
          ctx.moveTo(tx, br.sy - padPx);
          ctx.lineTo(tx, br.sy);
        }
        for (let ty = tl.sy; ty < tl.sy + padPx; ty += tileSize) {
          ctx.moveTo(tl.sx + padPx, ty);
          ctx.lineTo(br.sx - padPx, ty);
        }
        for (let ty = br.sy - padPx; ty < br.sy; ty += tileSize) {
          ctx.moveTo(tl.sx + padPx, ty);
          ctx.lineTo(br.sx - padPx, ty);
        }
        ctx.stroke();
      }
    }
  }
}

function drawBuildings(ctx, camera, xCoords, yCoords) {
  const pad = 8;
  const sidewalkColor = "#2a2a2a";
  const sidewalkEdge = "#3a3a3a";
  const curbColor = "#444";

  for (let i = 0; i < xCoords.length - 1; i++) {
    for (let j = 0; j < yCoords.length - 1; j++) {
      const swLeft = xCoords[i] + HALF_ROAD;
      const swRight = xCoords[i + 1] - HALF_ROAD;
      const swBottom = yCoords[j] + HALF_ROAD;
      const swTop = yCoords[j + 1] - HALF_ROAD;
      if (swRight <= swLeft || swTop <= swBottom) continue;

      const tl = worldToScreen(swLeft, swTop, camera);
      const br = worldToScreen(swRight, swBottom, camera);
      const w = br.sx - tl.sx;
      const h = br.sy - tl.sy;

      ctx.fillStyle = sidewalkColor;
      ctx.fillRect(tl.sx, tl.sy, w, h);

      ctx.strokeStyle = sidewalkEdge;
      ctx.lineWidth = 1;
      ctx.strokeRect(tl.sx, tl.sy, w, h);

      if (camera.zoom > 0.5) {
        const padPx = pad * camera.zoom;
        ctx.strokeStyle = curbColor;
        ctx.lineWidth = Math.max(1, 1.5 * camera.zoom);
        ctx.beginPath();
        ctx.moveTo(tl.sx + padPx, tl.sy);
        ctx.lineTo(tl.sx + padPx, tl.sy + h);
        ctx.moveTo(br.sx - padPx, tl.sy);
        ctx.lineTo(br.sx - padPx, tl.sy + h);
        ctx.moveTo(tl.sx, tl.sy + padPx);
        ctx.lineTo(tl.sx + w, tl.sy + padPx);
        ctx.moveTo(tl.sx, br.sy - padPx);
        ctx.lineTo(tl.sx + w, br.sy - padPx);
        ctx.stroke();

        const tileSize = 8 * camera.zoom;
        if (tileSize > 3) {
          ctx.strokeStyle = "rgba(255,255,255,0.04)";
          ctx.lineWidth = 0.5;
          ctx.beginPath();
          for (let tx = tl.sx; tx < tl.sx + padPx; tx += tileSize) {
            ctx.moveTo(tx, tl.sy);
            ctx.lineTo(tx, tl.sy + h);
          }
          for (let ty = tl.sy; ty < tl.sy + h; ty += tileSize) {
            ctx.moveTo(tl.sx, ty);
            ctx.lineTo(tl.sx + padPx, ty);
          }
          for (let tx = br.sx - padPx; tx < br.sx; tx += tileSize) {
            ctx.moveTo(tx, tl.sy);
            ctx.lineTo(tx, tl.sy + h);
          }
          for (let ty = tl.sy; ty < tl.sy + h; ty += tileSize) {
            ctx.moveTo(br.sx - padPx, ty);
            ctx.lineTo(br.sx, ty);
          }
          for (let tx = tl.sx + padPx; tx < br.sx - padPx; tx += tileSize) {
            ctx.moveTo(tx, tl.sy);
            ctx.lineTo(tx, tl.sy + padPx);
            ctx.moveTo(tx, br.sy - padPx);
            ctx.lineTo(tx, br.sy);
          }
          for (let ty = tl.sy; ty < tl.sy + padPx; ty += tileSize) {
            ctx.moveTo(tl.sx + padPx, ty);
            ctx.lineTo(br.sx - padPx, ty);
          }
          for (let ty = br.sy - padPx; ty < br.sy; ty += tileSize) {
            ctx.moveTo(tl.sx + padPx, ty);
            ctx.lineTo(br.sx - padPx, ty);
          }
          ctx.stroke();
        }
      }
    }
  }

  const blocks = [];
  for (let i = 0; i < xCoords.length - 1; i++) {
    for (let j = 0; j < yCoords.length - 1; j++) {
      const blockLeft = xCoords[i] + HALF_ROAD + pad;
      const blockRight = xCoords[i + 1] - HALF_ROAD - pad;
      const blockBottom = yCoords[j] + HALF_ROAD + pad;
      const blockTop = yCoords[j + 1] - HALF_ROAD - pad;
      if (blockRight <= blockLeft || blockTop <= blockBottom) continue;
      blocks.push({ blockLeft, blockRight, blockBottom, blockTop, i, j });
    }
  }

  if (_buildingImagesLoaded && blocks.length > 0) {
    const imageGrid = [
      [2, 0, 4, 3],   // bottom row
      [3, 4, 0, 2],   // row 1
      [4, 2, 0, 3],   // row 2
      [0, 3, 4, 2],   // top row
    ];
    for (let bi = 0; bi < blocks.length; bi++) {
      const b = blocks[bi];
      const col = b.i % imageGrid[0].length;
      const row = b.j % imageGrid.length;
      const imgIdx = imageGrid[row][col];
      const img = _buildingImages[imgIdx];

      const tl = worldToScreen(b.blockLeft, b.blockTop, camera);
      const br = worldToScreen(b.blockRight, b.blockBottom, camera);
      const drawW = br.sx - tl.sx;
      const drawH = br.sy - tl.sy;

      if (drawW > 1 && drawH > 1) {
        ctx.drawImage(img, tl.sx, tl.sy, drawW, drawH);
      }

      ctx.strokeStyle = COLORS.buildingEdge;
      ctx.lineWidth = 1;
      ctx.strokeRect(tl.sx, tl.sy, drawW, drawH);
    }
  } else {
    for (const b of blocks) {
      const tl = worldToScreen(b.blockLeft, b.blockTop, camera);
      const br = worldToScreen(b.blockRight, b.blockBottom, camera);

      ctx.fillStyle = COLORS.building;
      ctx.strokeStyle = COLORS.buildingEdge;
      ctx.lineWidth = 1;
      ctx.fillRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);
      ctx.strokeRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);
    }
  }
}

function drawIntersectionDetail(ctx, camera, ix, iy, bounds) {
  const tl = worldToScreen(ix - HALF_ROAD, iy + HALF_ROAD, camera);
  const br = worldToScreen(ix + HALF_ROAD, iy - HALF_ROAD, camera);
  ctx.fillStyle = COLORS.road;
  ctx.fillRect(tl.sx, tl.sy, br.sx - tl.sx, br.sy - tl.sy);

  if (camera.zoom < 0.4) return;

  const cwOffset = HALF_ROAD + 8;
  const cwLen = 10;
  const lineGap = 2;
  const lineThick = 0.6;
  const numStrips = Math.max(2, Math.floor((ROAD_WIDTH * camera.zoom) / (8 * camera.zoom)));

  const singleNode = bounds && bounds.minX === bounds.maxX && bounds.minY === bounds.maxY;
  const hasTop = !bounds || singleNode || iy < bounds.maxY;
  const hasBottom = !bounds || singleNode || iy > bounds.minY;
  const hasLeft = !bounds || singleNode || ix > bounds.minX;
  const hasRight = !bounds || singleNode || ix < bounds.maxX;

  const lineColor = "rgba(255,255,255,0.7)";
  const stripColor = "rgba(255,255,255,0.85)";

  if (hasTop) {
    ctx.fillStyle = lineColor;
    let a = worldToScreen(ix - HALF_ROAD + 2, iy + cwOffset - lineGap, camera);
    let b = worldToScreen(ix + HALF_ROAD - 2, iy + cwOffset - lineGap - lineThick, camera);
    ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
    a = worldToScreen(ix - HALF_ROAD + 2, iy + cwOffset + cwLen + lineGap + lineThick, camera);
    b = worldToScreen(ix + HALF_ROAD - 2, iy + cwOffset + cwLen + lineGap, camera);
    ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
  }
  if (hasBottom) {
    ctx.fillStyle = lineColor;
    let a = worldToScreen(ix - HALF_ROAD + 2, iy - cwOffset + lineGap + lineThick, camera);
    let b = worldToScreen(ix + HALF_ROAD - 2, iy - cwOffset + lineGap, camera);
    ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
    a = worldToScreen(ix - HALF_ROAD + 2, iy - cwOffset - cwLen - lineGap, camera);
    b = worldToScreen(ix + HALF_ROAD - 2, iy - cwOffset - cwLen - lineGap - lineThick, camera);
    ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
  }
  if (hasLeft) {
    ctx.fillStyle = lineColor;
    let a = worldToScreen(ix - cwOffset + lineGap, iy - HALF_ROAD + 2, camera);
    let b = worldToScreen(ix - cwOffset + lineGap + lineThick, iy + HALF_ROAD - 2, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    a = worldToScreen(ix - cwOffset - cwLen - lineGap - lineThick, iy - HALF_ROAD + 2, camera);
    b = worldToScreen(ix - cwOffset - cwLen - lineGap, iy + HALF_ROAD - 2, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
  }
  if (hasRight) {
    ctx.fillStyle = lineColor;
    let a = worldToScreen(ix + cwOffset - lineGap - lineThick, iy - HALF_ROAD + 2, camera);
    let b = worldToScreen(ix + cwOffset - lineGap, iy + HALF_ROAD - 2, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    a = worldToScreen(ix + cwOffset + cwLen + lineGap, iy - HALF_ROAD + 2, camera);
    b = worldToScreen(ix + cwOffset + cwLen + lineGap + lineThick, iy + HALF_ROAD - 2, camera);
    ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
  }

  ctx.fillStyle = stripColor;
  for (let s = 0; s < numStrips; s++) {
    const frac = (s + 0.5) / numStrips;
    const stripX = ix - HALF_ROAD + frac * ROAD_WIDTH;
    const stripY = iy - HALF_ROAD + frac * ROAD_WIDTH;

    if (hasTop) {
      let a = worldToScreen(stripX - 1.5, iy + cwOffset + cwLen, camera);
      let b = worldToScreen(stripX + 1.5, iy + cwOffset, camera);
      ctx.fillRect(a.sx, a.sy, b.sx - a.sx, b.sy - a.sy);
    }
    if (hasBottom) {
      let a = worldToScreen(stripX - 1.5, iy - cwOffset, camera);
      let b = worldToScreen(stripX + 1.5, iy - cwOffset - cwLen, camera);
      ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    }
    if (hasLeft) {
      let a = worldToScreen(ix - cwOffset - cwLen, stripY - 1.5, camera);
      let b = worldToScreen(ix - cwOffset, stripY + 1.5, camera);
      ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    }
    if (hasRight) {
      let a = worldToScreen(ix + cwOffset, stripY - 1.5, camera);
      let b = worldToScreen(ix + cwOffset + cwLen, stripY + 1.5, camera);
      ctx.fillRect(a.sx, b.sy, b.sx - a.sx, a.sy - b.sy);
    }
  }
}

function drawDemoHighlight(ctx, camera, demo, grid) {
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
    const isSingle = grid && grid.intersections && grid.intersections.length === 1;
    if (isSingle) {
      const extend = (grid.grid_spacing || 200) * 0.65;
      const topEdge = worldToScreen(demo.x, demo.y + extend + HALF_ROAD, camera);
      ctx.textAlign = "center";
      ctx.fillText("DEMO", topEdge.sx, topEdge.sy - 14);
    } else {
      ctx.textAlign = "center";
      ctx.fillText("DEMO", center.sx, center.sy - r - 4);
    }
  }
}

const CONGESTION_THRESHOLD = 4;
const CONGESTION_RADIUS = 60; // world units — how close a vehicle must be to count

function drawCongestedIntersections(ctx, camera, grid, agents) {
  if (!grid?.intersections) return;
  const vehicles = Object.values(agents).filter(a => a.agent_type === "vehicle");
  if (vehicles.length === 0) return;

  for (const inter of grid.intersections) {
    let count = 0;
    for (const v of vehicles) {
      const dx = v.x - inter.x;
      const dy = v.y - inter.y;
      if (dx * dx + dy * dy < CONGESTION_RADIUS * CONGESTION_RADIUS) {
        count++;
      }
    }
    if (count >= CONGESTION_THRESHOLD) {
      const center = worldToScreen(inter.x, inter.y, camera);
      const r = 75 * camera.zoom;
      const intensity = Math.min(1.0, (count - CONGESTION_THRESHOLD + 1) / 5);
      const alphaCore = 0.08 + 0.12 * intensity;
      const alphaMid = 0.04 + 0.06 * intensity;

      const grad = ctx.createRadialGradient(center.sx, center.sy, 0, center.sx, center.sy, r);
      grad.addColorStop(0, `rgba(244, 67, 54, ${alphaCore})`);
      grad.addColorStop(0.7, `rgba(244, 67, 54, ${alphaMid})`);
      grad.addColorStop(1, "rgba(244, 67, 54, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(center.sx, center.sy, r, 0, Math.PI * 2); ctx.fill();

      if (camera.zoom > 0.45) {
        ctx.fillStyle = `rgba(244, 67, 54, ${0.4 + 0.3 * intensity})`;
        ctx.font = `bold ${Math.max(8, 10 * camera.zoom)}px monospace`;
        ctx.textAlign = "center";
        ctx.fillText(`⚠ ${count} vehicles`, center.sx, center.sy - r - 4);
      }
    }
  }
}

function drawTrafficLights(ctx, camera, phase, demo) {
  if (!phase || !demo) return;
  const ix = demo.x, iy = demo.y;
  const r = Math.max(3, 5 * camera.zoom);
  const pad = 2 * camera.zoom;
  const dist = HALF_ROAD + 18;

  const lights = [
    { wx: ix - HALF_ROAD - 8, wy: iy + dist, green: phase === "NS_GREEN", angle: Math.PI },
    { wx: ix + HALF_ROAD + 8, wy: iy - dist, green: phase === "NS_GREEN", angle: 0 },
    { wx: ix + dist, wy: iy + HALF_ROAD + 8, green: phase === "EW_GREEN", angle: -Math.PI / 2 },
    { wx: ix - dist, wy: iy - HALF_ROAD - 8, green: phase === "EW_GREEN", angle: Math.PI / 2 },
  ];

  for (const pos of lights) {
    const s = worldToScreen(pos.wx, pos.wy, camera);
    const boxW = r * 2 + pad * 2, boxH = r * 4 + pad * 3;

    ctx.save();
    ctx.translate(s.sx, s.sy);
    ctx.rotate(pos.angle);

    ctx.fillStyle = "#111"; ctx.strokeStyle = "#444"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(-boxW / 2, -boxH / 2, boxW, boxH, 3);
    ctx.fill(); ctx.stroke();

    ctx.fillStyle = pos.green ? "#00e676" : "#1a3a1a";
    ctx.beginPath(); ctx.arc(0, -r - pad / 2, r, 0, Math.PI * 2); ctx.fill();
    if (pos.green) { ctx.shadowColor = "#00e676"; ctx.shadowBlur = 6; ctx.fill(); ctx.shadowBlur = 0; }

    ctx.fillStyle = pos.green ? "#3a1a1a" : "#f44336";
    ctx.beginPath(); ctx.arc(0, r + pad / 2, r, 0, Math.PI * 2); ctx.fill();
    if (!pos.green) { ctx.shadowColor = "#f44336"; ctx.shadowBlur = 6; ctx.fill(); ctx.shadowBlur = 0; }

    ctx.restore();
  }
}

function drawVehicle(ctx, camera, agent) {
  const s = worldToScreen(agent.x, agent.y, camera);
  const decision = agent.decision || "go";
  const speedKmh = (agent.speed || 0) * 3.6;
  const effectiveDecision = (decision === "brake" || decision === "stop")
    ? (speedKmh > 5 ? "brake" : "stop")
    : decision;
  let color;
  if (agent.is_drunk) color = COLORS.drunk;
  else if (agent.is_police) color = COLORS.police;       // solid blue body
  else if (agent.is_emergency) color = COLORS.emergency;  // solid red body
  else if (effectiveDecision === "go") color = COLORS.vehicle_go;
  else if (effectiveDecision === "yield") color = COLORS.vehicle_yield;
  else if (effectiveDecision === "brake") color = COLORS.vehicle_brake;
  else color = COLORS.vehicle_stop;

  const isBg = agent.agent_id?.startsWith("BG_") || agent.agent_id?.startsWith("AMBULANCE_") || agent.agent_id?.startsWith("POLICE_");
  const isDrunk = agent.is_drunk;

  if (isDrunk) { ctx.shadowColor = COLORS.drunk; ctx.shadowBlur = 18; }
  else if (agent.is_police) { ctx.shadowColor = COLORS.police; ctx.shadowBlur = 14; }
  else if (agent.risk_level === "collision") { ctx.shadowColor = COLORS.emergency; ctx.shadowBlur = 20; }
  else if (agent.risk_level === "high") { ctx.shadowColor = "#ff9800"; ctx.shadowBlur = 12; }

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

  if (agent.is_police) {
    const policeFlash = Math.sin(Date.now() / 120) > 0; // fast alternation
    const leftColor = policeFlash ? "#ff1744" : "#0055ff";
    const rightColor = policeFlash ? "#0055ff" : "#ff1744";
    ctx.save();
    ctx.translate(s.sx, s.sy);
    ctx.rotate((agent.direction * Math.PI) / 180);
    const dotR = 2.2 * camera.zoom;
    ctx.fillStyle = leftColor;
    ctx.shadowColor = leftColor;
    ctx.shadowBlur = 12 * camera.zoom;
    ctx.beginPath(); ctx.arc(-w / 2 + 1 * camera.zoom, -h / 2 + 2 * camera.zoom, dotR, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = rightColor;
    ctx.shadowColor = rightColor;
    ctx.shadowBlur = 12 * camera.zoom;
    ctx.beginPath(); ctx.arc(w / 2 - 1 * camera.zoom, -h / 2 + 2 * camera.zoom, dotR, 0, Math.PI * 2); ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
  }
  else if (agent.is_emergency && !agent.is_drunk) {
    const ambuFlash = Math.sin(Date.now() / 150) > 0;
    if (ambuFlash) {
      ctx.save();
      ctx.translate(s.sx, s.sy);
      ctx.rotate((agent.direction * Math.PI) / 180);
      const dotR = 2 * camera.zoom;
      ctx.fillStyle = "#2979ff";
      ctx.shadowColor = "#2979ff";
      ctx.shadowBlur = 12 * camera.zoom;
      ctx.beginPath(); ctx.arc(-w / 2 + 1 * camera.zoom, -h / 2 + 2 * camera.zoom, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(w / 2 - 1 * camera.zoom, -h / 2 + 2 * camera.zoom, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();
    }
  }

  if (agent.pulling_over) {
    const isClearing = agent.reason === "clearing_intersection_for_emergency";
    const flash = Math.sin(Date.now() / 150) > 0; // fast blink
    if (flash) {
      ctx.save();
      ctx.translate(s.sx, s.sy);
      ctx.rotate((agent.direction * Math.PI) / 180);
      ctx.strokeStyle = isClearing ? "#00e5ff" : "#ffab00";
      ctx.lineWidth = 2.5 * camera.zoom;
      ctx.beginPath();
      ctx.roundRect(-w / 2 - 2 * camera.zoom, -h / 2 - 2 * camera.zoom, w + 4 * camera.zoom, h + 4 * camera.zoom, 3 * camera.zoom);
      ctx.stroke();
      ctx.fillStyle = isClearing ? "#00e5ff" : "#ffab00";
      const dotR = 1.5 * camera.zoom;
      ctx.beginPath(); ctx.arc(-w / 2, -h / 2, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(w / 2, -h / 2, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(-w / 2, h / 2, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(w / 2, h / 2, dotR, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    if (camera.zoom > 0.5) {
      ctx.fillStyle = isClearing ? "#00e5ff" : "#ffab00";
      ctx.font = `bold ${Math.max(8, 9 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(isClearing ? "⚡ CLEARING" : "⚠ PULL OVER", s.sx, s.sy - h - 4 * camera.zoom);
    }
  }

  if (camera.zoom > 0.6) {
    if (isDrunk) {
      if (agent.arrested) {
        const arrestFlash = Math.sin(Date.now() / 150) > 0;
        ctx.save();
        ctx.translate(s.sx, s.sy);
        ctx.rotate((agent.direction * Math.PI) / 180);
        ctx.strokeStyle = arrestFlash ? "#0055ff" : "#ff1744";
        ctx.lineWidth = 2.5 * camera.zoom;
        ctx.setLineDash([4 * camera.zoom, 3 * camera.zoom]);
        ctx.beginPath();
        ctx.roundRect(-w / 2 - 2 * camera.zoom, -h / 2 - 2 * camera.zoom, w + 4 * camera.zoom, h + 4 * camera.zoom, 3 * camera.zoom);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
        ctx.fillStyle = arrestFlash ? "#ff1744" : "#0055ff";
        ctx.font = `bold ${Math.max(9, 10 * camera.zoom)}px monospace`;
        ctx.textAlign = "center";
        ctx.fillText("ARRESTED", s.sx, s.sy + h + 6 * camera.zoom);
      } else {
        ctx.fillStyle = COLORS.drunk;
        ctx.font = `bold ${Math.max(9, 10 * camera.zoom)}px monospace`;
        ctx.textAlign = "center";
        ctx.fillText("DRUNK", s.sx, s.sy + h + 6 * camera.zoom);
        ctx.fillStyle = "#FF69B4";
        if (agent.reason && agent.reason !== "drunk_driving") {
          ctx.fillStyle = "#FF69B4";
          ctx.fillText(agent.reason.toUpperCase(), s.sx, s.sy + h + 25 * camera.zoom);
        }
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
      const displayLabel = agent.agent_id?.startsWith("AMBULANCE_") ? "AMBULANCE"
        : agent.agent_id?.startsWith("POLICE_") ? "POLICE"
        : agent.agent_id;
      ctx.fillStyle = agent.agent_id?.startsWith("AMBULANCE_") ? COLORS.emergency
        : agent.agent_id?.startsWith("POLICE_") ? COLORS.police
        : "rgba(255,255,255,0.5)";
      ctx.font = `bold ${Math.max(7, 8 * camera.zoom)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(displayLabel, s.sx, s.sy + h + 6 * camera.zoom);
      if (agent.is_police && (agent.reason === "chasing_drunk" || agent.reason === "arresting_drunk")) {
        const chaseFlash = Math.sin(Date.now() / 200) > 0;
        ctx.fillStyle = chaseFlash ? "#ff1744" : "#0055ff";
        ctx.font = `bold ${Math.max(7, 8 * camera.zoom)}px monospace`;
        ctx.fillText(agent.reason === "arresting_drunk" ? "ARRESTING" : "CHASING", s.sx, s.sy + h + 15 * camera.zoom);
      } else if (agent.decision && agent.decision !== "go") {
        ctx.fillStyle = color;
        ctx.font = `bold ${Math.max(6, 7 * camera.zoom)}px monospace`;
        ctx.fillText(effectiveDecision.toUpperCase(), s.sx, s.sy + h + 15 * camera.zoom);
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

const DEFAULT_GRID = {
  intersections: [{ x: 0, y: 0 }],
  grid_cols: 1, grid_rows: 1, grid_spacing: 300,
  demo_intersection: { x: 0, y: 0 },
};

export default function IntersectionMap({
  agents = {}, infrastructure = {}, collisionPairs = [],
  grid = null, fullScreen = false,
  externalZoom = null, onMinZoom = null, onZoomChange = null,
  trafficLightIntersections = [],
  activeMode = 'SCENARIO',
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 0.6, canvasW: 800, canvasH: 600 });
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0 });
  const gridData = grid || DEFAULT_GRID;

  const positionsRef = useRef({});
  const lastUpdateTimeRef = useRef(performance.now());
  const rafRef = useRef(null);
  const latestPropsRef = useRef({ agents, infrastructure, collisionPairs, trafficLightIntersections });

  useEffect(() => {
    latestPropsRef.current = { agents, infrastructure, collisionPairs, trafficLightIntersections };
  }, [agents, infrastructure, collisionPairs, trafficLightIntersections]);

  useEffect(() => {
    const now = performance.now();
    const prev = positionsRef.current;
    const next = {};
    for (const [id, agent] of Object.entries(agents)) {
      if (agent.agent_type !== "vehicle") continue;
      const old = prev[id];
      if (old) {
        next[id] = { prevX: old.currX, prevY: old.currY, currX: agent.x, currY: agent.y };
      } else {
        next[id] = { prevX: agent.x, prevY: agent.y, currX: agent.x, currY: agent.y };
      }
    }
    positionsRef.current = next;
    lastUpdateTimeRef.current = now;
  }, [agents]);

  const computeMinZoom = useCallback(() => {
    const g = gridData;
    if (!g.intersections || g.intersections.length < 2) return 0.8;
    const xs = g.intersections.map(i => i.x);
    const ys = g.intersections.map(i => i.y);
    const worldW = (Math.max(...xs) - Math.min(...xs)) + g.grid_spacing * 1.2;
    const worldH = (Math.max(...ys) - Math.min(...ys)) + g.grid_spacing * 1.2;
    const zx = camera.canvasW / worldW;
    const zy = camera.canvasH / worldH;
    return Math.max(0.1, Math.min(zx, zy));
  }, [gridData, camera.canvasW, camera.canvasH]);

  useEffect(() => {
    if (externalZoom !== null && externalZoom !== undefined) {
      const minZ = computeMinZoom();
      setCamera(prev => ({ ...prev, zoom: Math.max(minZ, externalZoom) }));
    }
  }, [externalZoom, computeMinZoom]);

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

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setCamera(prev => {
      const minZ = computeMinZoom();
      const maxZ = 3.0;
      const newZoom = Math.max(minZ, Math.min(maxZ, prev.zoom * delta));
      if (onZoomChange) onZoomChange(newZoom);
      return { ...prev, zoom: newZoom };
    });
  }, [computeMinZoom, onZoomChange]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

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

  const cameraRef = useRef(camera);
  useEffect(() => { cameraRef.current = camera; }, [camera]);

  const activeModeRef = useRef(activeMode);
  useEffect(() => { activeModeRef.current = activeMode; }, [activeMode]);

  const gridDataRef = useRef(gridData);
  useEffect(() => { gridDataRef.current = gridData; }, [gridData]);

  useEffect(() => {
    const UPDATE_MS = 50;

    const renderFrame = () => {
      const canvas = canvasRef.current;
      if (!canvas) { rafRef.current = requestAnimationFrame(renderFrame); return; }
      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      const cam = { ...cameraRef.current };
      const gd = gridDataRef.current;
      const { agents: curAgents, infrastructure: curInfra, collisionPairs: curPairs, trafficLightIntersections: curTLI } = latestPropsRef.current;

      canvas.width = cam.canvasW * dpr;
      canvas.height = cam.canvasH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const now = performance.now();
      const elapsed = now - lastUpdateTimeRef.current;
      const t = Math.min(elapsed / UPDATE_MS, 1.0);

      const interpolatedAgents = {};
      for (const [id, agent] of Object.entries(curAgents)) {
        const pos = positionsRef.current[id];
        if (pos) {
          interpolatedAgents[id] = {
            ...agent,
            x: pos.prevX + (pos.currX - pos.prevX) * t,
            y: pos.prevY + (pos.currY - pos.prevY) * t,
          };
        } else {
          interpolatedAgents[id] = agent;
        }
      }

      ctx.clearRect(0, 0, cam.canvasW, cam.canvasH);
      drawCityGrid(ctx, cam, gd);
      if (activeModeRef.current !== 'CITY') {
        drawDemoHighlight(ctx, cam, gd.demo_intersection, gd);
      }
      drawCollisionZone(ctx, cam, curPairs, interpolatedAgents);

      const bgV = [], demoV = [], drunkV = [];
      for (const a of Object.values(interpolatedAgents)) {
        if (a.agent_type !== "vehicle") continue;
        if (a.is_drunk) drunkV.push(a);
        else if (a.agent_id?.startsWith("BG_") || a.agent_id?.startsWith("AMBULANCE_") || a.agent_id?.startsWith("POLICE_")) bgV.push(a);
        else demoV.push(a);
      }
      for (const v of bgV) drawVehicle(ctx, cam, v);
      for (const v of demoV) drawVehicle(ctx, cam, v);
      for (const v of drunkV) drawVehicle(ctx, cam, v);

      drawCongestedIntersections(ctx, cam, gd, interpolatedAgents);

      if (curInfra?.phase) drawTrafficLights(ctx, cam, curInfra.phase, gd.demo_intersection);

      if (curTLI && curTLI.length > 0 && gd.intersections && gd.intersections.length > 1) {
        for (const tli of curTLI) {
          if (curInfra?.phase && gd.demo_intersection &&
              tli.x === gd.demo_intersection.x && tli.y === gd.demo_intersection.y) continue;
          drawTrafficLights(ctx, cam, tli.phase, tli);
        }
      }

      rafRef.current = requestAnimationFrame(renderFrame);
    };

    rafRef.current = requestAnimationFrame(renderFrame);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, []);

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
