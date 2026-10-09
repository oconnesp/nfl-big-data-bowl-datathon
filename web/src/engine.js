// Square Yards Surrendered (SYS) engine. Same method as pocket_accountability/compute.py:
// every frame, sample a 5-yd disk around the QB on a 0.25-yd grid; a point is lost to the
// nearest rusher who is strictly closer than the QB; each rusher's area beyond what he held
// at the snap (clipped at 0) is charged to his PFF blocker(s), split evenly, or to UNBLOCKED.
export const R = 5, RES = 0.25, CELL = RES * RES, N = Math.round(R / RES), M = 2 * N + 1;

export function buildGrid() {
  const ox = [], oy = [], ii = [], jj = [];
  const index = new Int32Array(M * M).fill(-1);
  for (let i = -N; i <= N; i++) for (let j = -N; j <= N; j++) {
    if (i * i + j * j > N * N) continue; // integer test keeps the point count exact
    index[(i + N) * M + (j + N)] = ox.length;
    ox.push(i * RES); oy.push(j * RES); ii.push(i); jj.push(j);
  }
  return { n: ox.length, ox: Float64Array.from(ox), oy: Float64Array.from(oy), ii: Int16Array.from(ii), jj: Int16Array.from(jj), index };
}
export const GRID = buildGrid();
export const FULL = GRID.n * CELL;

/** Grid index of the point nearest to an offset (gx, gy) from the QB, or -1 outside the disk. */
export function gridIndexAt(gx, gy) {
  const i = Math.round(gx / RES), j = Math.round(gy / RES);
  if (i * i + j * j > N * N) return -1;
  return GRID.index[(i + N) * M + (j + N)];
}

/** Computes ownership and SYS for every frame of a play in the pipeline's replay format. */
export function computeTimeline(play) {
  const qb = play.players.find(p => p.side === 'QB');
  const rushers = play.players.filter(p => p.side === 'RUSH');
  const blockers = play.players.filter(p => p.side === 'BLOCK');
  const bIds = new Set(blockers.map(b => String(b.nflId)));
  // Valid blockers only; ["UNBLOCKED"], empty or unknown ids all route to UNBLOCKED.
  const by = rushers.map(r => [...new Set(((play.assign || {})[r.nflId] || []).map(String))].filter(id => bIds.has(id)));
  const nR = rushers.length, G = GRID, frames = [];
  let base = null, maxSys = 0;
  for (const f of play.frames) {
    const q = f.pos[qb.nflId];
    if (!q) throw new Error(`no QB position at t=${f.t}`);
    const rs = rushers.map(r => { const p = f.pos[r.nflId]; if (!p) throw new Error(`no position for rusher ${r.nflId} at t=${f.t}`); return p; });
    const owner = new Int8Array(G.n), lost = new Float64Array(nR);
    for (let i = 0; i < G.n; i++) {
      const gx = G.ox[i], gy = G.oy[i], px = q[0] + gx, py = q[1] + gy;
      let best = -1, bd = gx * gx + gy * gy; // squared distances keep the strict "<" rule
      for (let k = 0; k < nR; k++) {
        const dx = px - rs[k][0], dy = py - rs[k][1], d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = k; }
      }
      owner[i] = best;
      if (best >= 0) lost[best] += CELL;
    }
    if (!base) base = Float64Array.from(lost);
    const charged = new Float64Array(nR), sys = { UNBLOCKED: 0 };
    for (const b of blockers) sys[b.nflId] = 0;
    let lostAll = 0;
    for (let k = 0; k < nR; k++) {
      lostAll += lost[k];
      const c = Math.max(0, lost[k] - base[k]);
      charged[k] = c;
      if (by[k].length) for (const id of by[k]) sys[id] += c / by[k].length;
      else sys.UNBLOCKED += c;
    }
    for (const v of Object.values(sys)) if (v > maxSys) maxSys = v;
    frames.push({ t: f.t, q, rs, owner, lost, charged, sys, pocket: G.n * CELL - lostAll });
  }
  return { qb, rushers, blockers, by, frames, maxSys, hasUnblocked: by.some(b => b.length === 0) };
}
