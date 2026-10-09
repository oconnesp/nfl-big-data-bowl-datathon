// Shape checks for the three data files. Each returns a list of "path: problem" strings.
export function validateReplays(d) {
  const e = [];
  if (!Array.isArray(d)) return ['$: expected an array of plays'];
  if (!d.length) return ['$: no plays in the file'];
  d.forEach((p, i) => {
    const at = `$[${i}]`;
    if (!p || typeof p !== 'object') { e.push(`${at}: expected an object`); return; }
    if (!p.meta || !Number.isFinite(p.meta.gameId) || !Number.isFinite(p.meta.playId)) e.push(`${at}.meta: gameId and playId must be numbers`);
    if (!Array.isArray(p.players)) { e.push(`${at}.players: expected an array`); return; }
    const qbs = p.players.filter(x => x && x.side === 'QB').length;
    if (qbs !== 1) e.push(`${at}.players: expected exactly 1 QB, found ${qbs}`);
    if (!p.players.some(x => x && x.side === 'RUSH')) e.push(`${at}.players: no pass rushers`);
    const ids = p.players.map(x => String(x && x.nflId));
    if (!Array.isArray(p.frames) || !p.frames.length) { e.push(`${at}.frames: expected a non-empty array`); return; }
    p.frames.forEach((f, j) => {
      if (!f || !Number.isFinite(f.t)) { e.push(`${at}.frames[${j}].t: expected a number`); return; }
      if (j && !(f.t > p.frames[j - 1].t)) e.push(`${at}.frames[${j}].t: frames must increase in time`);
      for (const id of ids) {
        const v = f.pos && f.pos[id];
        if (!Array.isArray(v) || !Number.isFinite(v[0]) || !Number.isFinite(v[1])) { e.push(`${at}.frames[${j}].pos.${id}: missing or non-finite position`); break; }
      }
    });
    for (const [rid, list] of Object.entries(p.assign || {})) {
      if (!ids.includes(rid)) e.push(`${at}.assign.${rid}: unknown rusher nflId`);
      if (!Array.isArray(list)) { e.push(`${at}.assign.${rid}: expected an array`); continue; }
      list.forEach((b, m) => { if (b !== 'UNBLOCKED' && !ids.includes(String(b))) e.push(`${at}.assign.${rid}[${m}]: unknown blocker nflId ${b}`); });
    }
  });
  return e;
}

export function validateLeaderboard(d) {
  const e = [];
  if (!d || typeof d !== 'object' || !Array.isArray(d.players)) return ['$.players: expected an array'];
  d.players.forEach((p, i) => {
    const at = `$.players[${i}]`;
    for (const k of ['name', 'team', 'position']) if (typeof p[k] !== 'string' || !p[k]) e.push(`${at}.${k}: expected a non-empty string`);
    for (const k of ['nflId', 'snaps', 'sys25', 'positionAvg', 'percentile']) if (!Number.isFinite(p[k])) e.push(`${at}.${k}: expected a number`);
    if (p.byWeek != null && !Array.isArray(p.byWeek)) e.push(`${at}.byWeek: expected an array`);
  });
  return e;
}

export function validateValidation(d) {
  const e = [];
  if (!d || typeof d !== 'object') return ['$: expected an object'];
  if (!Array.isArray(d.headlines) || !d.headlines.length) e.push('$.headlines: expected a non-empty array');
  else d.headlines.forEach((h, i) => {
    if (typeof h.label !== 'string' || !h.label) e.push(`$.headlines[${i}].label: expected a string`);
    if (h.value == null || h.value === '') e.push(`$.headlines[${i}].value: missing`);
  });
  if (!Array.isArray(d.charts)) e.push('$.charts: expected an array');
  else d.charts.forEach((c, i) => {
    if (!['bar', 'line', 'scatter'].includes(c.type)) e.push(`$.charts[${i}].type: expected bar, line or scatter`);
    if (!Array.isArray(c.series)) { e.push(`$.charts[${i}].series: expected an array`); return; }
    c.series.forEach((s, j) => {
      if (!Array.isArray(s.points) || s.points.some(p => !Array.isArray(p) || !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) e.push(`$.charts[${i}].series[${j}].points: expected [x, y] number pairs`);
    });
  });
  return e;
}
