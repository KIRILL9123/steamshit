import type { PlayerMovementPoint } from '@/types/domain';
import { MAP_METADATA } from '@/constants/maps';

export function shortAngleDist(a0: number, a1: number): number {
  const maxAngle = 360;
  const difference = (a1 - a0) % maxAngle;
  return ((2 * difference) % maxAngle) - difference;
}

export function getInterpolatedPosition(playerMovementArray: PlayerMovementPoint[], targetTick: number) {
  if (!playerMovementArray || playerMovementArray.length === 0) return null;
  
  let prev: PlayerMovementPoint | null = null;
  let next: PlayerMovementPoint | null = null;
  
  for (let i = 0; i < playerMovementArray.length; i++) {
    const pt = playerMovementArray[i];
    if (pt.tick <= targetTick) {
      prev = pt;
    } else {
      next = pt;
      break;
    }
  }
  
  if (!prev) {
    return playerMovementArray[0];
  }
  if (!next) {
    return prev;
  }
  
  const denom = next.tick - prev.tick;
  if (denom === 0) return prev;
  
  const alpha = (targetTick - prev.tick) / denom;
  
  const px = prev.x !== null && next.x !== null ? prev.x + (next.x - prev.x) * alpha : prev.x;
  const py = prev.y !== null && next.y !== null ? prev.y + (next.y - prev.y) * alpha : prev.y;
  const pz = prev.z !== null && next.z !== null ? prev.z + (next.z - prev.z) * alpha : prev.z;
  
  let pyaw = prev.yaw;
  if (prev.yaw !== null && next.yaw !== null) {
    const diff = shortAngleDist(prev.yaw, next.yaw);
    pyaw = (prev.yaw + diff * alpha) % 360;
    if (pyaw < 0) pyaw += 360;
  }
  
  return {
    player: prev.player,
    tick: targetTick,
    x: px,
    y: py,
    z: pz,
    yaw: pyaw,
    health: prev.health,
    is_alive: prev.is_alive
  };
}

export interface RenderFrameOptions {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  round: { roundNum: number; freezeEndTick?: number | null; startTick: number | null; endTick?: number | null };
  currentTick: number;
  kills: any[];
  grenades: any[];
  groupedMovements: Record<string, PlayerMovementPoint[]>;
  playersDetail: any[];
  mapName: string | null | undefined;
  mapImage: HTMLImageElement | null;
  mapImageLoaded: boolean;
}

export function renderReplayFrame(opt: RenderFrameOptions) {
  const {
    ctx,
    width: W,
    height: H,
    round,
    currentTick,
    kills,
    grenades,
    groupedMovements,
    playersDetail,
    mapName,
    mapImage,
    mapImageLoaded,
  } = opt;

  ctx.clearRect(0, 0, W, H);

  if (!round) {
    ctx.fillStyle = 'rgba(170,175,185,0.35)';
    ctx.font = '13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Выберите раунд', W / 2, H / 2);
    return;
  }

  const roundStartTick = round.freezeEndTick ?? round.startTick ?? 0;
  const absTick = roundStartTick + currentTick;
  const totalTicks = Math.max((round.endTick ?? 0) - roundStartTick, 0);

  // Gather all positions for bounds fallback
  const allXs: number[] = [];
  const allYs: number[] = [];
  for (const k of kills) {
    if (k.attackerX != null) { allXs.push(k.attackerX); }
    if (k.victimX != null) { allXs.push(k.victimX); }
    if (k.attackerY != null) { allYs.push(k.attackerY); }
    if (k.victimY != null) { allYs.push(k.victimY); }
  }
  for (const g of grenades) {
    if (g.throwX != null) { allXs.push(g.throwX); if (g.throwY != null) allYs.push(g.throwY); }
    if (g.landX != null) { allXs.push(g.landX); if (g.landY != null) allYs.push(g.landY); }
  }

  const hasPositions = allXs.length > 0;

  if (!hasPositions) {
    // Text-mode: no coordinate data, show kill feed as list
    ctx.fillStyle = 'rgba(170,175,185,0.4)';
    ctx.font = '13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`Раунд ${round.roundNum} — нет данных о позициях`, W / 2, H / 2 - 28);
    ctx.font = '11px Inter, sans-serif';
    ctx.fillText(`Всего убийств: ${kills.length}`, W / 2, H / 2 - 6);

    const visibles = kills.filter((k) => {
      if (k.tick == null) return currentTick >= totalTicks / 2;
      return k.tick <= absTick;
    });

    ctx.textAlign = 'left';
    ctx.font = '11px monospace';
    let ly = H / 2 + 20;
    for (const k of visibles.slice(-10)) {
      const hs = k.headshot ? ' · HS' : '';
      const wb = k.wallbang ? ' · WB' : '';
      ctx.fillStyle = k.headshot ? '#FF8C00' : 'rgba(230,232,240,0.75)';
      ctx.fillText(`${k.attacker} → ${k.victim}  [${k.weapon}]${hs}${wb}`, W / 2 - 200, ly);
      ly += 17;
    }
    return;
  }

  const pad = 32;
  const minX = Math.min(...allXs), maxX = Math.max(...allXs);
  const minY = Math.min(...allYs), maxY = Math.max(...allYs);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const dW = W - pad * 2;
  const dH = H - pad * 2;

  let tx = (x: number) => pad + ((x - minX) / rangeX) * dW;
  let ty = (y: number) => pad + ((maxY - y) / rangeY) * dH;

  const metadata = mapName ? MAP_METADATA[mapName] : null;

  if (metadata && mapImage && mapImageLoaded) {
    const size = Math.min(W, H);
    const offsetX = (W - size) / 2;
    const offsetY = (H - size) / 2;

    // Draw background map
    ctx.drawImage(mapImage, offsetX, offsetY, size, size);

    // Override projection functions to match radar dimensions (1024x1024)
    tx = (x: number) => {
      const pxX = (x - metadata.posX) / metadata.scale;
      return offsetX + (pxX / 1024) * size;
    };
    ty = (y: number) => {
      const pxY = (metadata.posY - y) / metadata.scale;
      return offsetY + (pxY / 1024) * size;
    };
  } else {
    // Fallback: draw grid
    ctx.strokeStyle = 'rgba(255,255,255,0.035)';
    ctx.lineWidth = 1;
    const gs = 48;
    for (let x = 0; x < W; x += gs) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += gs) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
  }

  // ── Draw grenade arcs ────────────────────────────────────────────────────
  for (const g of grenades) {
    if (g.throwX == null || g.throwY == null || g.landX == null || g.landY == null) continue;
    const color =
      g.nadeType === 'smoke' ? '#00C2FF' :
      g.nadeType === 'flash' ? '#F0B43C' :
      g.nadeType === 'he' || g.nadeType === 'grenade' ? '#E64646' :
      '#a78bfa';
    ctx.save();
    ctx.strokeStyle = color + '55';
    ctx.setLineDash([3, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(tx(g.throwX), ty(g.throwY));
    ctx.lineTo(tx(g.landX), ty(g.landY));
    ctx.stroke();
    ctx.setLineDash([]);
    // Landing glow
    const lg = ctx.createRadialGradient(tx(g.landX), ty(g.landY), 0, tx(g.landX), ty(g.landY), 8);
    lg.addColorStop(0, color + '80');
    lg.addColorStop(1, color + '00');
    ctx.fillStyle = lg;
    ctx.beginPath();
    ctx.arc(tx(g.landX), ty(g.landY), 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // ── Draw kills up to current tick ─────────────────────────────────────────
  const visibleKills = kills.filter((k) => {
    if (k.tick == null) return currentTick >= totalTicks / 2;
    return k.tick <= absTick;
  });

  for (const k of visibleKills) {
    const ax = k.attackerX != null ? tx(k.attackerX) : null;
    const ay = k.attackerY != null ? ty(k.attackerY) : null;
    const vx = k.victimX != null ? tx(k.victimX) : null;
    const vy = k.victimY != null ? ty(k.victimY) : null;

    // Kill line
    if (ax != null && ay != null && vx != null && vy != null) {
      ctx.save();
      ctx.strokeStyle = k.headshot ? 'rgba(255,140,0,0.45)' : 'rgba(240,240,242,0.18)';
      ctx.lineWidth = k.headshot ? 1.5 : 1;
      ctx.setLineDash([2, 5]);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(vx, vy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }

    // Attacker dot (orange)
    if (ax != null && ay != null) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(ax, ay, 6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,140,0,0.55)';
      ctx.fill();
      ctx.strokeStyle = '#FF8C00';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.restore();
    }

    // Victim × (red cross)
    if (vx != null && vy != null) {
      ctx.save();
      ctx.strokeStyle = '#E64646';
      ctx.lineWidth = 2;
      const s = 5;
      ctx.beginPath();
      ctx.moveTo(vx - s, vy - s); ctx.lineTo(vx + s, vy + s);
      ctx.moveTo(vx + s, vy - s); ctx.lineTo(vx - s, vy + s);
      ctx.stroke();
      ctx.restore();
    }
  }

  // Interpolate current positions
  const currentMovements: any[] = [];
  const players = Object.keys(groupedMovements);
  for (const player of players) {
    const pt = getInterpolatedPosition(groupedMovements[player], absTick);
    if (pt) {
      currentMovements.push(pt);
    }
  }

  // ── Draw player positions ────────────────────────────────────────────────
  for (const p of currentMovements) {
    if (!p.is_alive || p.x == null || p.y == null) continue;
    const px = tx(p.x);
    const py = ty(p.y);

    ctx.save();

    // Draw direction arrow (yaw)
    if (p.yaw != null) {
      const rad = (p.yaw * Math.PI) / 180;
      const dx_dir = Math.cos(rad);
      const dy_dir = -Math.sin(rad);

      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px + dx_dir * 12, py + dy_dir * 12);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      const arrowSize = 4;
      const angleLeft = rad + (135 * Math.PI) / 180;
      const angleRight = rad - (135 * Math.PI) / 180;

      const tipX = px + dx_dir * 12;
      const tipY = py + dy_dir * 12;

      ctx.beginPath();
      ctx.moveTo(tipX, tipY);
      ctx.lineTo(tipX + Math.cos(angleLeft) * arrowSize, tipY - Math.sin(angleLeft) * arrowSize);
      ctx.lineTo(tipX + Math.cos(angleRight) * arrowSize, tipY - Math.sin(angleRight) * arrowSize);
      ctx.closePath();
      ctx.fillStyle = '#ffffff';
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(px, py, 5.5, 0, Math.PI * 2);

    // Color code by team
    const playerDetail = playersDetail?.find((pl) => pl.name === p.player);
    const team = playerDetail?.team?.toLowerCase();
    const color = team === 'ct' ? '#3b82f6' : team === 't' ? '#f59e0b' : '#10b981';

    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw health bar border/background
    const hw = 14;
    const hh = 3;
    const hx = px - hw / 2;
    const hy = py + 7;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(hx, hy, hw, hh);
    // Draw health green fill
    ctx.fillStyle = '#22c55e';
    ctx.fillRect(hx, hy, hw * (p.health / 100), hh);

    // Draw player name tag
    ctx.fillStyle = '#ffffff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(p.player, px, py - 9);
    ctx.restore();
  }

  // ── Round info overlay ────────────────────────────────────────────────────
  ctx.save();
  ctx.fillStyle = 'rgba(230,232,240,0.65)';
  ctx.font = 'bold 11px Inter, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText(`Раунд ${round.roundNum}`, pad, pad - 18);
  ctx.fillStyle = 'rgba(170,175,185,0.5)';
  ctx.font = '10px Inter, sans-serif';
  ctx.fillText(
    `Убийств показано: ${visibleKills.length} / ${kills.length}`,
    pad,
    pad - 4
  );
  ctx.restore();
}
