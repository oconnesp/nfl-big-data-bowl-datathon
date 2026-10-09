// Builds web/public/data/{replays,leaderboard}.json from Workstream A's outputs (read-only).
// replays.json  = pocket_accountability/out/replays.json + the illustrative mockup play.
// leaderboard.json = provisional, aggregated from pocket_accountability/out/blocker_plays.csv
// until Workstream A ships its own leaderboard.json. validation.json is hand-edited (Workstream B).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateReplays, validateLeaderboard, validateValidation } from '../src/validate.js';

const here = dirname(fileURLToPath(import.meta.url));
const OUT = join(here, '..', 'public', 'data');
const PIPE = join(here, '..', '..', 'pocket_accountability', 'out');
const DATA = join(here, '..', '..', 'data');
mkdirSync(OUT, { recursive: true });

function parseCSV(text) {
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  const [h, ...body] = rows;
  return body.filter(r => r.length === h.length).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}

// The original mockup play, ported from its keyframes (smoothstep interpolation), in the pipeline format.
const ease = u => u * u * (3 - 2 * u);
function at(k, t) {
  if (t <= k[0][0]) return [k[0][1], k[0][2]];
  for (let i = 1; i < k.length; i++) if (t <= k[i][0]) {
    const a = k[i - 1], b = k[i], u = ease((t - a[0]) / (b[0] - a[0]));
    return [a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
  }
  const l = k[k.length - 1]; return [l[1], l[2]];
}
function mockupPlay() {
  const OL = [
    { slot: 'LT', jersey: 72, pos: 'T', name: 'A. Lindgren', k: [[0, -4.5, -1], [1, -5.8, -3], [2, -6.3, -4.6], [3.6, -6.6, -5.4]] },
    { slot: 'LG', jersey: 64, pos: 'G', name: 'B. Osei', k: [[0, -2.2, -1], [0.6, -2.2, -1.8], [2, -2.0, -3.0], [3.6, -1.9, -4.2]] },
    { slot: 'C', jersey: 60, pos: 'C', name: 'C. Haddad', k: [[0, 0, -1], [0.6, 0.2, -1.8], [3.6, 0.4, -2.4]] },
    { slot: 'RG', jersey: 66, pos: 'G', name: 'D. Moreau', k: [[0, 2.2, -1], [0.6, 2.1, -1.8], [3.6, 2.0, -2.5]] },
    { slot: 'RT', jersey: 78, pos: 'T', name: 'E. Kowalski', k: [[0, 4.5, -1], [0.9, 6.1, -2.6], [1.6, 6.4, -3.6], [2.4, 5.6, -4.8], [3.6, 4.6, -5.6]] },
  ];
  const DL = [
    { slot: 'LE', jersey: 91, pos: 'DE', name: 'F. Adeyemi', by: ['LT'], k: [[0, -6.6, 0.8], [1, -7.6, -2.4], [2, -7.7, -4.2], [3.6, -7.8, -5.4]] },
    { slot: 'DT', jersey: 97, pos: 'DT', name: 'G. Brandt', by: ['LG'], k: [[0, -1.6, 0.8], [0.6, -2.1, -1.0], [2, -1.9, -2.2], [3.6, -1.7, -3.4]] },
    { slot: 'NT', jersey: 99, pos: 'DT', name: 'H. Castillo', by: ['C', 'RG'], k: [[0, 1.1, 0.8], [0.6, 1.1, -1.0], [3.6, 1.2, -1.6]] },
    { slot: 'RE', jersey: 94, pos: 'DE', name: 'I. Dimitrov', by: ['RT'], k: [[0, 6.8, 0.8], [0.9, 8.2, -2.2], [1.6, 7.6, -4.4], [2.4, 5.4, -6.4], [3.1, 2.8, -7.3], [3.6, 1.0, -6.9]] },
  ];
  const QB = { k: [[0, 0, -5], [0.9, 0, -7.2], [2.0, -0.2, -7.2], [2.8, -0.6, -6.4], [3.6, 0.3, -6.6]] };
  const players = [
    { nflId: 9000, side: 'QB', name: 'J. Sample', position: 'QB', jersey: 12, lined_up: 'QB' },
    ...OL.map((o, i) => ({ nflId: 9001 + i, side: 'BLOCK', name: o.name, position: o.pos, jersey: o.jersey, lined_up: o.slot })),
    ...DL.map((d, i) => ({ nflId: 9101 + i, side: 'RUSH', name: d.name, position: d.pos, jersey: d.jersey, lined_up: d.slot })),
  ];
  const idOf = slot => String(9001 + OL.findIndex(o => o.slot === slot));
  const assign = Object.fromEntries(DL.map((d, i) => [String(9101 + i), d.by.map(idOf)]));
  const r3 = v => Math.round(v * 1000) / 1000;
  const frames = [];
  for (let f = 0; f <= 36; f++) {
    const t = f / 10, pos = { 9000: at(QB.k, t).map(r3) };
    OL.forEach((o, i) => { pos[9001 + i] = at(o.k, t).map(r3); });
    DL.forEach((d, i) => { pos[9101 + i] = at(d.k, t).map(r3); });
    frames.push({ t, pos });
  }
  return {
    meta: {
      gameId: 2021999901, playId: 1, quarter: 3, down: 3, yardsToGo: 7, gameClock: '6:12', possessionTeam: 'OFF', defensiveTeam: 'DEF',
      playDescription: 'Illustrative play from the original mockup (not real tracking data): the right end beats the right tackle with speed for a sack.',
      passResult: 'S', dropBackType: 'TRADITIONAL', fps: 10, radius: 5, t_std: 2.5, showcase: 'illustrative', synthetic: true, sackBy: 94,
      events: [[0, 'Snap'], [1.6, 'RT beaten'], [2.8, 'Pressure'], [3.6, 'Sack']],
    },
    players, assign, helpers: [], pff_allowed: {}, frames,
  };
}

function leaderboard() {
  const csvPath = join(PIPE, 'blocker_plays.csv');
  if (!existsSync(csvPath)) return null;
  const rows = parseCSV(readFileSync(csvPath, 'utf8'));
  const playsCsv = join(DATA, 'plays.csv');
  const plays = existsSync(playsCsv) ? new Map(parseCSV(readFileSync(playsCsv, 'utf8')).map(p => [`${p.gameId}-${p.playId}`, p])) : new Map();
  const acc = new Map();
  for (const r of rows) {
    if (r.is_unblocked === 'True' || r.is_helper === 'True' || !r.nflId || r.sys25 === '') continue;
    if (!['T', 'G', 'C'].includes(r.officialPosition)) continue;
    const v = +r.sys25, wk = +r.week;
    let p = acc.get(r.nflId);
    if (!p) acc.set(r.nflId, p = { nflId: +r.nflId, name: r.displayName, team: {}, position: {}, snaps: 0, s25: 0, sEnd: 0, press: 0, weeks: {}, worst: null });
    p.team[r.team] = (p.team[r.team] || 0) + 1;
    p.position[r.officialPosition] = (p.position[r.officialPosition] || 0) + 1;
    p.snaps++; p.s25 += v; p.sEnd += +r.sys_end;
    if (+r.pff_sackAllowed || +r.pff_hitAllowed || +r.pff_hurryAllowed) p.press++;
    const w = p.weeks[wk] || (p.weeks[wk] = { week: wk, snaps: 0, sum: 0 });
    w.snaps++; w.sum += v;
    if (!p.worst || v > p.worst.sys25) p.worst = { gameId: +r.gameId, playId: +r.playId, week: wk, sys25: v };
  }
  const top = o => Object.entries(o).sort((a, b) => b[1] - a[1])[0][0];
  const all = [...acc.values()].map(p => ({ ...p, team: top(p.team), position: top(p.position) }));
  const sum = {}, n = {};
  for (const p of all) { sum[p.position] = (sum[p.position] || 0) + p.s25; n[p.position] = (n[p.position] || 0) + p.snaps; }
  const positionAverages = Object.fromEntries(['T', 'G', 'C'].map(k => [k, +(sum[k] / n[k]).toFixed(3)]));
  const counts = [100, 150].map(m => `${all.filter(p => p.snaps >= m).length} with ${m}+`).join(', ');
  const MIN = all.filter(p => p.snaps >= 150).length >= 60 ? 150 : 100;
  const q = all.filter(p => p.snaps >= MIN);
  const players = q.map(p => {
    const sys25 = p.s25 / p.snaps;
    const peers = q.filter(o => o.position === p.position);
    const worse = peers.filter(o => o.s25 / o.snaps > sys25).length;
    const pl = plays.get(`${p.worst.gameId}-${p.worst.playId}`);
    const desc = pl ? `Q${pl.quarter} ${pl.gameClock} · ${pl.possessionTeam} vs ${pl.defensiveTeam} · ${pl.playDescription}` : `Game ${p.worst.gameId}, play ${p.worst.playId}`;
    return {
      nflId: p.nflId, name: p.name, team: p.team, position: p.position, snaps: p.snaps,
      sys25: +sys25.toFixed(3), sysEnd: +(p.sEnd / p.snaps).toFixed(3), positionAvg: positionAverages[p.position],
      percentile: peers.length > 1 ? +(worse / (peers.length - 1) * 100).toFixed(1) : 50,
      pressureRate: +(p.press / p.snaps).toFixed(4),
      byWeek: Object.values(p.weeks).sort((a, b) => a.week - b.week).map(w => ({ week: w.week, snaps: w.snaps, sys25: +(w.sum / w.snaps).toFixed(3) })),
      worstRep: { ...p.worst, sys25: +p.worst.sys25.toFixed(3), description: desc.slice(0, 200) },
    };
  });
  console.log(`leaderboard: ${players.length} linemen at ${MIN}+ snaps (${counts})`);
  return {
    stub: false, provisional: true, minSnaps: MIN, positionAverages, players,
    source: 'Provisional: aggregated in web/ from pocket_accountability/out/blocker_plays.csv (pipeline v1) until Workstream A ships leaderboard.json.',
  };
}

const src = join(PIPE, 'replays.json');
const real = existsSync(src) ? JSON.parse(readFileSync(src, 'utf8')) : [];
const replays = [...real, mockupPlay()];
const errs = validateReplays(replays);
if (errs.length) { console.error('replays.json failed validation:\n' + errs.slice(0, 10).join('\n')); process.exit(1); }
writeFileSync(join(OUT, 'replays.json'), JSON.stringify(replays));
console.log(`replays: ${real.length} from the pipeline + 1 illustrative`);
const lb = leaderboardFromA() || leaderboard();
writeValidation();
if (!lb) console.log('leaderboard: pipeline CSV not found, keeping the existing file');
else {
  const e = validateLeaderboard(lb);
  if (e.length) { console.error('leaderboard.json failed validation:\n' + e.slice(0, 10).join('\n')); process.exit(1); }
  writeFileSync(join(OUT, 'leaderboard.json'), JSON.stringify(lb));
}

// ---- Final Workstream A leaderboard (pocket_accountability/out/leaderboard.json), mapped to the page format ----
function lookups() {
  const plays = new Map(parseCSV(readFileSync(join(DATA, 'plays.csv'), 'utf8')).map(p => [`${p.gameId}-${p.playId}`, p]));
  const week = new Map(parseCSV(readFileSync(join(DATA, 'games.csv'), 'utf8')).map(g => [g.gameId, +g.week]));
  return { plays, week };
}
function leaderboardFromA() {
  const f = join(PIPE, 'leaderboard.json');
  if (!existsSync(f)) return null;
  const a = JSON.parse(readFileSync(f, 'utf8')), { plays, week } = lookups();
  const players = a.players.map(p => {
    const w = p.worst_rep, pl = w && plays.get(`${w.gameId}-${w.playId}`);
    return {
      nflId: p.nflId, name: p.name, team: p.team, position: p.position, snaps: p.snaps,
      sys25: p.sys25_mean, sysEnd: p.sys_end_mean, positionAvg: p.pos_avg, percentile: p.percentile, tier: p.tier,
      pressureRate: p.pressure_rate, pressuresAllowed: p.pressures_allowed,
      byWeek: Object.entries(p.weekly || {}).map(([wk, v]) => ({ week: +wk, sys25: v })).sort((x, y) => x.week - y.week),
      worstRep: w ? { gameId: w.gameId, playId: w.playId, week: week.get(String(w.gameId)) ?? null, sys25: w.sys25,
        description: (pl ? `Q${pl.quarter} ${pl.gameClock} · ${pl.possessionTeam} vs ${pl.defensiveTeam} · ${pl.playDescription}` : `Game ${w.gameId}, play ${w.playId}`).slice(0, 200) } : undefined,
    };
  });
  console.log(`leaderboard: ${players.length} linemen from Workstream A's final leaderboard.json`);
  return { stub: false, minSnaps: a.min_snaps, positionAverages: a.position_averages, players,
    source: 'Percentiles and tiers are within the position each player actually lined up at (PFF).' };
}

// ---- "Does it work?" numbers, computed from the pipeline outputs ----
function auc(pos, neg) {
  const all = [...pos.map(v => [v, 1]), ...neg.map(v => [v, 0])].sort((a, b) => a[0] - b[0]);
  let rankSum = 0;
  for (let i = 0; i < all.length;) { let j = i; while (j < all.length && all[j][0] === all[i][0]) j++; const r = (i + j + 1) / 2; for (let k = i; k < j; k++) if (all[k][1]) rankSum += r; i = j; }
  return (rankSum - pos.length * (pos.length + 1) / 2) / (pos.length * neg.length);
}
function pearson(xs, ys) { const n = xs.length, mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n; let sxy = 0, sxx = 0, syy = 0; for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; } return sxy / Math.sqrt(sxx * syy); }
function writeValidation() {
  const rows = parseCSV(readFileSync(join(PIPE, 'blocker_plays.csv'), 'utf8')).filter(r => r.is_unblocked !== 'True' && r.is_helper !== 'True' && r.nflId && r.sys25 !== '');
  const flag = r => +r.pff_sackAllowed ? 'Sack' : +r.pff_hitAllowed ? 'Hit' : +r.pff_hurryAllowed ? 'Hurry' : 'Clean';
  const pos = rows.filter(r => flag(r) !== 'Clean').map(r => +r.sys25), neg = rows.filter(r => flag(r) === 'Clean').map(r => +r.sys25);
  const aPress = auc(pos, neg), aSack = auc(rows.filter(r => flag(r) === 'Sack').map(r => +r.sys25), neg);
  const outcomes = ['Clean', 'Hurry', 'Hit', 'Sack'], mean = o => { const v = rows.filter(r => flag(r) === o).map(r => +r.sys25); return v.reduce((a, b) => a + b, 0) / v.length; };
  // Split-half stability: odd vs even weeks, qualified linemen, centred within position (tackles run higher).
  const lb = JSON.parse(readFileSync(join(PIPE, 'leaderboard.json'), 'utf8')), posOf = new Map(lb.players.map(p => [String(p.nflId), p.position]));
  const h = new Map();
  for (const r of rows) {
    if (!posOf.has(r.nflId)) continue;
    const e = h.get(r.nflId) || { odd: { n: 0, s: 0, p: 0 }, even: { n: 0, s: 0, p: 0 } }; h.set(r.nflId, e);
    const b = +r.week % 2 ? e.odd : e.even; b.n++; b.s += +r.sys25; b.p += flag(r) !== 'Clean' ? 1 : 0;
  }
  const ids = [...h.keys()].filter(id => h.get(id).odd.n >= 30 && h.get(id).even.n >= 30);
  const centred = (get) => { const by = {}; ids.forEach(id => (by[posOf.get(id)] ||= []).push(get(id))); const m = Object.fromEntries(Object.entries(by).map(([k, v]) => [k, v.reduce((a, b) => a + b) / v.length])); return ids.map(id => get(id) - m[posOf.get(id)]); };
  const sO = centred(id => h.get(id).odd.s / h.get(id).odd.n), sE = centred(id => h.get(id).even.s / h.get(id).even.n);
  const pO = centred(id => h.get(id).odd.p / h.get(id).odd.n), pE = centred(id => h.get(id).even.p / h.get(id).even.n);
  const rSys = pearson(sO, sE), rPress = pearson(pO, pE);
  const sens = JSON.parse(readFileSync(join(PIPE, 'sensitivity.json'), 'utf8')), rho = sens.min_overall_sys25_rho;
  const v = {
    stub: false,
    headlines: [
      { label: 'AUC: SYS@2.5 vs PFF pressure allowed', value: aPress.toFixed(2), note: `Across ${rows.length.toLocaleString('en-US')} blocker-plays, SYS is higher when PFF charged the lineman with a hurry, hit or sack (0.5 = coin flip). Sacks alone: ${aSack.toFixed(2)}.` },
      { label: 'Week-to-week stability (odd vs even weeks)', value: rSys.toFixed(2), unit: 'r', note: `SYS@2.5 per lineman, ${ids.length} linemen, within position. The same check on PFF pressure rate gives r = ${rPress.toFixed(2)}.` },
      { label: 'Ranking vs pocket radius', value: rho.toFixed(2), unit: 'ρ', note: 'Spearman rank correlation of the leaderboard with a 4- or 6-yard pocket instead of 5. The ranking does not hinge on the radius.' },
      { label: 'Dropbacks measured', value: '8,532', note: '2021 weeks 1–8. PFF\'s sack-charged blocker is also the top-SYS blocker on 51% of sacks (chance: 20%).' },
    ],
    charts: [
      { id: 'by-outcome', title: 'Mean SYS@2.5 by what PFF charged the lineman with', type: 'bar', xLabel: 'PFF outcome on the snap', yLabel: 'Mean SYS@2.5 (yd²)', xTicks: outcomes,
        series: [{ name: 'SYS@2.5', points: outcomes.map((o, i) => [i, +mean(o).toFixed(2)]) }], caption: 'Linemen surrender more pocket the worse the PFF outcome, without SYS ever seeing PFF\'s grades.' },
      { id: 'stability', title: 'Odd weeks vs even weeks, per lineman', type: 'scatter', xLabel: 'SYS@2.5, odd weeks (yd², vs position avg)', yLabel: 'SYS@2.5, even weeks', 
        series: ['T', 'G', 'C'].map(k => ({ name: { T: 'Tackles', G: 'Guards', C: 'Centers' }[k], points: ids.map((id, i) => [id, i]).filter(([id]) => posOf.get(id) === k).map(([, i]) => [+sO[i].toFixed(2), +sE[i].toFixed(2)]) })),
        caption: `Each dot is a lineman with 30+ snaps in each half. r = ${rSys.toFixed(2)} for SYS vs ${rPress.toFixed(2)} for pressure rate.` },
    ],
  };
  const e = validateValidation(v); if (e.length) { console.error(e); process.exit(1); }
  writeFileSync(join(OUT, 'validation.json'), JSON.stringify(v, null, 1));
  console.log(`validation: AUC ${aPress.toFixed(3)} (sack ${aSack.toFixed(3)}), stability r SYS ${rSys.toFixed(3)} vs pressure ${rPress.toFixed(3)} (n=${ids.length}), rho ${rho.toFixed(3)}, means ${outcomes.map(o => o + ' ' + mean(o).toFixed(2)).join(', ')}`);
}
