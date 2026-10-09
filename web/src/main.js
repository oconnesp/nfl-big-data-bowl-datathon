import { GRID, R, RES, N, M, FULL, computeTimeline, gridIndexAt } from './engine.js';
import { validateReplays, validateLeaderboard, validateValidation } from './validate.js';

const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hexA = (hex, a) => { const n = parseInt(hex.replace('#', ''), 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; };
const SLOT_TOKEN = { LT: '--b-lt', LG: '--b-lg', C: '--b-c', RG: '--b-rg', RT: '--b-rt' };
const EXT = ['--b-x1', '--b-x2', '--b-x3', '--b-x4'];
const OUTCOME = { S: 'Sack', C: 'Complete', I: 'Incomplete', IN: 'Interception', R: 'Scramble' };
const SHOWCASE = { sack_hidden_culprit: 'SYS disagrees with PFF', clean_pocket: 'Clean pocket', stunt: 'Stunt', sack_culprit_confirmed: 'SYS agrees with PFF', unblocked: 'Free rusher', sack: 'Sack' };
const ord = n => ['', '1st', '2nd', '3rd', '4th'][n] || `${n}th`;
const short = name => { const p = String(name || '').split(' '); return p.length > 1 && !p[0].endsWith('.') ? `${p[0][0]}. ${p.slice(1).join(' ')}` : String(name || ''); };
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = { plays: [], idx: -1, play: null, tl: null, k: 0, cur: 0, playing: false, bcast: false, view: null, colors: {}, order: [], barIds: [], events: [], lb: null, pos: 'ALL', q: '' };
const stub = { replays: false, leaderboard: false, validation: false };

async function loadJSON(name) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(`data/${name}`, { signal: ctl.signal, cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = await r.text();
    try { return JSON.parse(text); } catch { throw new Error('not valid JSON'); }
  } catch (e) { throw new Error(`${name} could not be loaded (${e.name === 'AbortError' ? 'timed out after 10 s' : e.message})`); }
  finally { clearTimeout(timer); }
}
function fail(el, file, errs) {
  el.hidden = false;
  el.innerHTML = `<strong>${esc(file)}</strong> could not be shown.<ul>${errs.slice(0, 5).map(e => `<li><code>${esc(e)}</code></li>`).join('')}</ul>${errs.length > 5 ? `<p>…and ${errs.length - 5} more.</p>` : ''}`;
}

// ---------- play selection ----------
function playLabel(p) { const m = p.meta, tag = m.synthetic ? 'Illustrative mockup play' : SHOWCASE[m.showcase] || ''; return `${tag ? tag + ': ' : ''}${m.possessionTeam} vs ${m.defensiveTeam} · ${m.quarter > 4 ? 'OT' : 'Q' + m.quarter} ${ord(m.down)} & ${m.yardsToGo} · ${OUTCOME[m.passResult] || m.passResult}`; }
function setupPicker() {
  const sel = $('playPick');
  sel.innerHTML = S.plays.map((p, i) => `<option value="${i}">${esc(playLabel(p))}</option>`).join('');
  sel.disabled = false;
  sel.addEventListener('change', () => selectPlay(+sel.value));
  const want = new URLSearchParams(location.search).get('play');
  const i = S.plays.findIndex(p => `${p.meta.gameId}-${p.meta.playId}` === want);
  selectPlay(i >= 0 ? i : 0, false);
}
function selectPlay(i, writeUrl = true) {
  if (i === S.idx) return;
  stop();
  let tl;
  try { tl = computeTimeline(S.plays[i]); } catch (e) { fail($('replayErr'), 'replays.json', [`play ${i + 1}: ${e.message}`]); $('playPick').value = String(S.idx); return; }
  $('replayErr').hidden = true;
  S.idx = i; S.play = S.plays[i]; S.tl = tl; S.k = 0; S.cur = 0;
  const f0 = S.play.frames[0].pos;
  S.order = [...tl.blockers].sort((a, b) => f0[a.nflId][0] - f0[b.nflId][0]);
  S.colors = assignColors(S.order);
  S.view = computeView(S.play, tl);
  S.events = playEvents(S.play);
  S.sackBy = sackJersey(S.play, tl);
  $('playPick').value = String(i);
  if (writeUrl) { const u = new URL(location.href); u.searchParams.set('play', `${S.play.meta.gameId}-${S.play.meta.playId}`); history.replaceState(null, '', u); }
  renderPlayhead(); buildBars(); buildTicks();
  $('t').max = String(tl.frames.length - 1);
  resize(); set(0);
}
function assignColors(order) {
  const c = { UNBLOCKED: '--b-un' }, used = new Set(); let x = 0;
  for (const b of order) { const tok = SLOT_TOKEN[b.lined_up]; if (tok && !used.has(tok)) { c[b.nflId] = tok; used.add(tok); } }
  for (const b of order) if (!c[b.nflId]) c[b.nflId] = EXT[x++ % EXT.length];
  return c;
}
function computeView(play, tl) {
  let x0 = -12, x1 = 12, y0 = 3, y1 = -11;
  play.frames.forEach((f, k) => {
    for (const p of Object.values(f.pos)) { x0 = Math.min(x0, p[0] - 1); x1 = Math.max(x1, p[0] + 1); y0 = Math.max(y0, p[1] + 1); y1 = Math.min(y1, p[1] - 1); }
    const q = tl.frames[k].q; x0 = Math.min(x0, q[0] - R - 0.3); x1 = Math.max(x1, q[0] + R + 0.3); y1 = Math.min(y1, q[1] - R - 0.3);
  });
  const ratio = 24 / 14, w = x1 - x0, h = y0 - y1;
  if (w / h < ratio) { const nw = h * ratio, c = (x0 + x1) / 2; x0 = c - nw / 2; x1 = c + nw / 2; } else y1 = y0 - w / ratio;
  return { x0, x1, y0, y1 };
}
function playEvents(play) {
  const m = play.meta, last = play.frames.at(-1).t;
  if (Array.isArray(m.events)) return m.events.map(([t, l]) => [t, l]);
  const ev = [[0, 'Snap']];
  if (last > 3) ev.push([2.5, '2.5s']);
  ev.push([last, m.passResult === 'S' ? 'Sack' : m.passResult === 'R' ? 'Scramble' : 'Throw']);
  return ev;
}
function sackJersey(play, tl) {
  if (play.meta.passResult !== 'S') return null;
  if (play.meta.sackBy) return play.meta.sackBy;
  const m = /sacked[^(]*\(([^)]+)\)/.exec(play.meta.playDescription || '');
  if (!m) return null;
  const names = m[1].split(/[;,]/).map(s => s.trim().split('.').pop().trim().toLowerCase());
  const r = tl.rushers.find(x => names.includes(String(x.name).split(' ').pop().toLowerCase()));
  return r ? r.jersey : null;
}
function renderPlayhead() {
  const m = S.play.meta;
  $('sit').textContent = `${m.quarter > 4 ? 'OT' : 'Q' + m.quarter} · ${ord(m.down)} & ${m.yardsToGo} · ${m.gameClock} · ${m.possessionTeam} vs ${m.defensiveTeam}`;
  const pff = Object.entries(S.play.pff_allowed || {}).map(([id, what]) => {
    const b = S.tl.blockers.find(x => String(x.nflId) === id);
    return b ? `${what.join('/')} → ${b.lined_up || b.position} ${short(b.name)}` : null;
  }).filter(Boolean);
  $('res').textContent = `${S.tl.rushers.length}-man rush · ${OUTCOME[m.passResult] || m.passResult}${m.synthetic ? '' : pff.length ? ' · PFF charged: ' + pff.join(', ') : ' · PFF charged no one'}`;
  $('desc').textContent = m.playDescription || '';
  $('field').setAttribute('aria-label', `Top-down replay: ${playLabel(S.play)}. Space lost to each rusher is shaded in the colour of the blocker charged.`);
}
function buildBars() {
  const ids = S.order.map(b => ({ id: String(b.nflId), slot: b.lined_up || b.position, name: short(b.name) }));
  if (S.tl.hasUnblocked) ids.push({ id: 'UNBLOCKED', slot: 'FREE', name: 'Unblocked' });
  S.barIds = ids;
  $('bars').innerHTML = ids.map(b => `<div class="bar" data-id="${esc(b.id)}"><span class="who" title="${esc(b.name)}"><span class="sw${b.id === 'UNBLOCKED' ? ' hatch' : ''}" style="background-color:var(${S.colors[b.id]})"></span><b>${esc(b.slot)}</b><span class="nm">${esc(b.name)}</span></span><span class="track"><span class="fill${b.id === 'UNBLOCKED' ? ' hatch' : ''}" style="background-color:var(${S.colors[b.id]})"></span></span><span class="val">0.0</span></div>`).join('');
}
function buildTicks() {
  const last = S.tl.frames.at(-1).t || 1;
  $('ticks').innerHTML = S.events.map(([t, l], i, a) => `<span style="left:${(t / last * 100).toFixed(2)}%;${i === 0 ? 'transform:none' : i === a.length - 1 && t >= last - 1e-6 ? 'transform:translateX(-100%)' : ''}">${esc(l)}</span>`).join('');
}

// ---------- canvas ----------
const cv = $('field'), ctx = cv.getContext('2d'), tip = $('tip');
let W = 0, H = 0, SC = 1, hatch = null;
const X = x => (x - S.view.x0) * SC, Y = y => (S.view.y0 - y) * SC;
function setupCanvas() {
  const pc = document.createElement('canvas'); pc.width = pc.height = 6;
  const p = pc.getContext('2d'); p.strokeStyle = 'rgba(17,21,27,.8)'; p.lineWidth = 1.3;
  p.beginPath(); p.moveTo(0, 6); p.lineTo(6, 0); p.moveTo(-1, 1); p.lineTo(1, -1); p.moveTo(5, 7); p.lineTo(7, 5); p.stroke();
  hatch = ctx.createPattern(pc, 'repeat');
  new ResizeObserver(() => resize()).observe(cv);
  cv.addEventListener('pointermove', onHover);
  cv.addEventListener('pointerleave', () => { tip.hidden = true; });
  cv.addEventListener('keydown', onKey);
  $('t').addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); toggle(); } });
}
function resize() {
  const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (!r.width) return;
  W = r.width; H = r.height; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (S.view) SC = W / (S.view.x1 - S.view.x0);
  draw();
}
function disc(x, y, r, fill, stroke, label, txt) {
  ctx.beginPath(); ctx.arc(X(x), Y(y), r, 0, Math.PI * 2); ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.lineWidth = 2; ctx.strokeStyle = stroke; ctx.stroke(); }
  ctx.fillStyle = txt; ctx.font = `600 ${Math.max(8, r * (String(label).length > 3 ? 0.62 : 0.85))}px "Saira Semi Condensed", "Arial Narrow", sans-serif`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, X(x), Y(y) + 0.5);
}
function leader(fr) { let best = null; for (const b of S.barIds) { const v = fr.sys[b.id] || 0; if (v > (best ? best.v : 0) + 1e-12) best = { ...b, v }; } return best; }
function draw() {
  if (!W || !S.tl || !S.view) return;
  const tl = S.tl, fr = tl.frames[S.k], pos = S.play.frames[S.k].pos, V = S.view, q = fr.q;
  ctx.fillStyle = '#11151b'; ctx.fillRect(0, 0, W, H);
  for (let y = Math.ceil(V.y1); y <= Math.floor(V.y0); y++) {
    ctx.strokeStyle = y % 5 === 0 ? 'rgba(233,236,241,.16)' : 'rgba(233,236,241,.05)';
    ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0, Y(y)); ctx.lineTo(W, Y(y)); ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(111,155,255,.85)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, Y(0)); ctx.lineTo(W, Y(0)); ctx.stroke();
  ctx.fillStyle = 'rgba(111,155,255,.9)'; ctx.font = '500 11px "IBM Plex Mono", monospace'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
  ctx.fillText('LINE OF SCRIMMAGE', 8, Y(0) - 4);

  const col = {}; for (const [id, tok] of Object.entries(S.colors)) col[id] = css(tok);
  const cs = RES * SC + 0.6, a = S.bcast ? 0.85 : 0.62;
  for (let i = 0; i < GRID.n; i++) {
    const o = fr.owner[i], px = X(q[0] + GRID.ox[i] - RES / 2), py = Y(q[1] + GRID.oy[i] + RES / 2);
    if (o < 0) { ctx.fillStyle = S.bcast ? 'rgba(233,236,241,.34)' : 'rgba(233,236,241,.16)'; ctx.fillRect(px, py, cs, cs); continue; }
    const by = tl.by[o];
    if (!by.length) { ctx.fillStyle = hexA(col.UNBLOCKED, a); ctx.fillRect(px, py, cs, cs); ctx.fillStyle = hatch; ctx.fillRect(px, py, cs, cs); continue; }
    const b = by.length === 1 ? by[0] : by[(((GRID.ii[i] + GRID.jj[i]) % by.length) + by.length) % by.length]; // checkerboard for doubles
    ctx.fillStyle = hexA(col[b], a); ctx.fillRect(px, py, cs, cs);
  }
  if (S.bcast) outline(fr);
  else { ctx.setLineDash([4, 4]); ctx.strokeStyle = 'rgba(233,236,241,.45)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), R * SC, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }

  ctx.strokeStyle = 'rgba(230,103,103,.35)'; ctx.lineWidth = 1.5;
  tl.rushers.forEach((r, k) => { ctx.beginPath(); for (let j = 0; j <= S.k; j++) { const p = tl.frames[j].rs[k]; if (j) ctx.lineTo(X(p[0]), Y(p[1])); else ctx.moveTo(X(p[0]), Y(p[1])); } ctx.stroke(); });
  ctx.setLineDash([2, 4]); ctx.strokeStyle = 'rgba(233,236,241,.55)'; ctx.lineWidth = 1.2;
  tl.by.forEach((ids, k) => ids.forEach(id => { const o = pos[id]; if (!o) return; ctx.beginPath(); ctx.moveTo(X(o[0]), Y(o[1])); ctx.lineTo(X(fr.rs[k][0]), Y(fr.rs[k][1])); ctx.stroke(); }));
  ctx.setLineDash([]);
  const pr = Math.max(8, 0.45 * SC);
  S.order.forEach(b => { const p = pos[b.nflId]; disc(p[0], p[1], pr, col[b.nflId], '#11151b', b.lined_up || b.position, '#fff'); });
  tl.rushers.forEach((r, k) => disc(fr.rs[k][0], fr.rs[k][1], pr, '#11151b', '#e66767', r.jersey, '#f2f3f5'));
  disc(q[0], q[1], pr, '#f2f3f5', '#11151b', 'QB', '#11151b');
  if (S.k === tl.frames.length - 1 && S.play.meta.passResult === 'S') {
    ctx.fillStyle = '#e66767'; ctx.font = '700 15px "Saira Semi Condensed", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillText(S.sackBy ? `SACK · #${S.sackBy}` : 'SACK', X(q[0]), Y(q[1]) - pr - 8);
  }
  if (S.bcast) broadcastText(fr);
  renderRail();
}
function outline(fr) {
  // Boundary of the clean-pocket cells: draw every cell edge that faces a lost cell or the disk edge.
  const q = fr.q, h = RES / 2, clean = (i, j) => { if (i < -N || i > N || j < -N || j > N) return false; const g = GRID.index[(i + N) * M + (j + N)]; return g >= 0 && fr.owner[g] < 0; };
  ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5; ctx.beginPath();
  for (let g = 0; g < GRID.n; g++) {
    if (fr.owner[g] >= 0) continue;
    const i = GRID.ii[g], j = GRID.jj[g], cx = q[0] + i * RES, cy = q[1] + j * RES;
    if (!clean(i + 1, j)) { ctx.moveTo(X(cx + h), Y(cy - h)); ctx.lineTo(X(cx + h), Y(cy + h)); }
    if (!clean(i - 1, j)) { ctx.moveTo(X(cx - h), Y(cy - h)); ctx.lineTo(X(cx - h), Y(cy + h)); }
    if (!clean(i, j + 1)) { ctx.moveTo(X(cx - h), Y(cy + h)); ctx.lineTo(X(cx + h), Y(cy + h)); }
    if (!clean(i, j - 1)) { ctx.moveTo(X(cx - h), Y(cy - h)); ctx.lineTo(X(cx + h), Y(cy - h)); }
  }
  ctx.stroke();
}
function broadcastText(fr) {
  const num = fr.pocket.toFixed(1), L = leader(fr);
  ctx.fillStyle = 'rgba(10,12,16,.78)'; ctx.fillRect(12, 12, Math.min(W - 24, 360), 98);
  ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillStyle = '#f2f3f5'; ctx.font = '700 52px "Saira Semi Condensed", sans-serif'; ctx.fillText(num, 24, 16);
  const w = ctx.measureText(num).width;
  ctx.fillStyle = '#aab1bd'; ctx.font = '600 15px "Saira Semi Condensed", sans-serif'; ctx.fillText('YD² OF POCKET LEFT', 32 + w, 30);
  ctx.fillStyle = L && L.v > 2 ? '#ff8a8a' : '#aab1bd'; ctx.font = '600 15px "IBM Plex Sans", sans-serif';
  ctx.fillText(L ? `Most surrendered: ${L.slot} ${L.name} · ${L.v.toFixed(1)} yd²` : 'No space charged yet', 24, 82);
}

// ---------- rail ----------
function renderRail() {
  const tl = S.tl, fr = tl.frames[S.k], snap = tl.frames[0].pocket, L = leader(fr);
  $('pocket').innerHTML = `${fr.pocket.toFixed(1)}<small> yd²</small>`;
  $('pocketSub').textContent = `${snap > 0 ? Math.round(fr.pocket / snap * 100) : 0}% of the ${snap.toFixed(0)} yd² pocket at the snap`;
  $('bars').querySelectorAll('.bar').forEach(el => {
    const v = fr.sys[el.dataset.id] || 0;
    el.querySelector('.fill').style.width = (tl.maxSys > 0 ? v / tl.maxSys * 100 : 0) + '%';
    el.querySelector('.val').textContent = v.toFixed(1);
    el.classList.toggle('lead', !!L && L.id === el.dataset.id && L.v > 2);
  });
  $('leadNote').textContent = L && L.v > 2 ? `Most surrendered: ${L.slot} ${L.name} (${L.v.toFixed(1)} yd²)` : 'No blocker has given up more than 2 yd² yet';
  renderSpark();
}
function renderSpark() {
  const tl = S.tl, last = tl.frames.at(-1).t || 1, w = 284, h = 70, pad = { l: 26, r: 6, t: 6, b: 16 };
  const sx = v => pad.l + v / last * (w - pad.l - pad.r), sy = v => pad.t + (1 - v / FULL) * (h - pad.t - pad.b);
  const pts = tl.frames.map(f => `${sx(f.t).toFixed(1)},${sy(f.pocket).toFixed(1)}`).join(' ');
  const fr = tl.frames[S.k], ink = css('--muted'), acc = css('--accent'), line = css('--line');
  const secs = []; for (let s = 0; s <= last + 1e-9; s += last > 6 ? 2 : 1) secs.push(s);
  $('spark').innerHTML = `
    <line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(0)}" y2="${sy(0)}" stroke="${line}"/>
    <line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(FULL / 2)}" y2="${sy(FULL / 2)}" stroke="${line}" stroke-dasharray="2 3"/>
    <text x="${pad.l - 4}" y="${sy(FULL) + 4}" text-anchor="end" font-size="9" fill="${ink}">${Math.round(FULL)}</text>
    <text x="${pad.l - 4}" y="${sy(FULL / 2) + 3}" text-anchor="end" font-size="9" fill="${ink}">${Math.round(FULL / 2)}</text>
    <text x="${pad.l - 4}" y="${sy(0) + 3}" text-anchor="end" font-size="9" fill="${ink}">0</text>
    ${secs.map(s => `<text x="${sx(s)}" y="${h - 3}" text-anchor="middle" font-size="9" fill="${ink}">${s}s</text>`).join('')}
    <polygon points="${sx(0)},${sy(0)} ${pts} ${sx(last)},${sy(0)}" fill="${acc}" fill-opacity=".12"/>
    <polyline points="${pts}" fill="none" stroke="${acc}" stroke-width="2" stroke-linejoin="round"/>
    <line x1="${sx(fr.t)}" x2="${sx(fr.t)}" y1="${pad.t}" y2="${sy(0)}" stroke="${css('--fg')}" stroke-opacity=".35"/>
    <circle cx="${sx(fr.t)}" cy="${sy(fr.pocket)}" r="4" fill="${acc}" stroke="${css('--panel')}" stroke-width="2"/>`;
}

// ---------- playback ----------
let raf = 0, lastTs = 0;
function set(k) {
  const tl = S.tl; if (!tl) return;
  S.k = Math.max(0, Math.min(tl.frames.length - 1, k));
  const t = tl.frames[S.k].t; if (!S.playing) S.cur = t;
  const ev = S.events.find(([et]) => Math.abs(et - t) < 0.05);
  $('t').value = String(S.k); $('t').setAttribute('aria-valuetext', `${t.toFixed(1)} seconds${ev ? ', ' + ev[1] : ''}`);
  $('clock').textContent = t.toFixed(1) + 's';
  draw();
  if (ev && S.playing) announce();
  if (!S.playing) $('play').textContent = S.k === tl.frames.length - 1 ? 'Replay' : 'Play';
}
function loop(ts) {
  const dt = lastTs ? (ts - lastTs) / 1000 : 0; lastTs = ts;
  S.cur += dt * 0.75;
  const lastK = S.tl.frames.length - 1, k = Math.min(lastK, Math.floor(S.cur * 10 + 1e-6));
  if (k !== S.k) set(k);
  if (k >= lastK) { stop(); return; }
  raf = requestAnimationFrame(loop);
}
function stop() {
  if (raf) cancelAnimationFrame(raf);
  const was = S.playing; raf = 0; lastTs = 0; S.playing = false;
  if (S.tl) $('play').textContent = S.k === S.tl.frames.length - 1 ? 'Replay' : 'Play';
  if (was) announce();
}
function toggle() {
  if (!S.tl) return;
  if (S.playing) return stop();
  if (S.k >= S.tl.frames.length - 1) set(0);
  S.cur = S.tl.frames[S.k].t; S.playing = true; $('play').textContent = 'Pause'; raf = requestAnimationFrame(loop);
}
function announce() {
  const fr = S.tl.frames[S.k], L = leader(fr);
  $('live').textContent = `${fr.t.toFixed(1)} seconds: ${fr.pocket.toFixed(1)} square yards of pocket left. ${L ? `Most surrendered: ${L.slot} ${L.name}, ${L.v.toFixed(1)} square yards.` : 'No space charged yet.'}`;
}
function onKey(e) {
  if (!S.tl) return;
  const last = S.tl.frames.length - 1, step = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
  if (e.key === ' ') { e.preventDefault(); toggle(); }
  else if (step) { e.preventDefault(); stop(); set(S.k + step); }
  else if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); stop(); set(e.key === 'Home' ? 0 : last); }
}
function setBroadcast(on) { S.bcast = on; $('bcast').setAttribute('aria-pressed', String(on)); $('bcast').textContent = on ? 'Coach view' : 'Broadcast view'; draw(); }

// ---------- tooltip ----------
function onHover(e) {
  if (!S.tl) return;
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, fr = S.tl.frames[S.k];
  const g = gridIndexAt(mx / SC + S.view.x0 - fr.q[0], S.view.y0 - my / SC - fr.q[1]);
  if (g < 0) { tip.hidden = true; return; }
  const o = fr.owner[g];
  if (o < 0) tip.innerHTML = '<b>Clean pocket</b><br>QB reaches this spot first';
  else {
    const rs = S.tl.rushers[o], by = S.tl.by[o];
    const who = by.length ? by.map(id => { const b = S.tl.blockers.find(x => String(x.nflId) === id); return `${esc(b.lined_up || b.position)} ${esc(short(b.name))}`; }).join(' + ') + (by.length > 1 ? ' (split)' : '') : 'UNBLOCKED';
    tip.innerHTML = `<b>Lost to #${esc(rs.jersey)} ${esc(short(rs.name))} (${esc(rs.position)})</b><br>Charged to ${who}${fr.charged[o] === 0 ? '<br><span class="dim">No net ground gained since the snap · nothing charged yet</span>' : ''}`;
  }
  tip.hidden = false;
  tip.style.left = Math.max(6, Math.min(mx + 14, r.width - tip.offsetWidth - 6)) + 'px';
  tip.style.top = (my + cv.offsetTop + 14) + 'px';
}

// ---------- leaderboard + player panel ----------
const TIER = { Wall: 'g', Leaky: 'b', Average: 'm' };
const tier = p => p.tier && TIER[p.tier] ? [TIER[p.tier], p.tier] : p.percentile >= 75 ? ['g', 'Wall'] : p.percentile <= 25 ? ['b', 'Leaky'] : ['m', 'Average'];
function displayed() {
  if (!S.lb) return [];
  return S.lb.players.filter(p => (S.pos === 'ALL' || p.position === S.pos) && (!S.q || p.name.toLowerCase().includes(S.q) || p.team.toLowerCase().includes(S.q)))
    .sort((a, b) => a.sys25 - b.sys25 || a.name.localeCompare(b.name) || a.nflId - b.nflId);
}
function renderTable() {
  const rows = displayed();
  if (!rows.length) { $('rows').innerHTML = `<tr><td colspan="8" class="empty">${S.lb && S.lb.players.length ? 'No linemen match this filter' : 'No players met the minimum snap count'}</td></tr>`; return; }
  const spread = Math.max(0.5, ...rows.map(p => Math.abs(p.sys25 - p.positionAvg)));
  $('rows').innerHTML = rows.map((p, i) => {
    const d = p.sys25 - p.positionAvg, x = Math.max(2, Math.min(98, 50 + d / spread * 46)), t = tier(p);
    return `<tr tabindex="0" data-id="${p.nflId}" aria-label="${esc(p.name)}, ${esc(p.team)}: open player panel">
      <td>${i + 1}</td><td>${esc(p.name)} <span class="team">${esc(p.team)}</span></td><td>${esc(p.position)}</td>
      <td class="n">${p.snaps}</td><td class="n">${p.sys25.toFixed(1)}</td>
      <td class="dist"><div class="distbar" title="${d >= 0 ? '+' : ''}${d.toFixed(1)} yd² vs ${esc(p.position)} average"><b></b><i style="left:calc(${x.toFixed(1)}% - 1.5px)"></i></div></td>
      <td class="n">${Math.round(p.percentile)}</td><td><span class="grade ${t[0]}">${t[1]}</span></td></tr>`;
  }).join('');
}
function setupLeaderboardUI() {
  $('search').addEventListener('input', () => { S.q = $('search').value.trim().toLowerCase(); renderTable(); });
  document.querySelectorAll('.chips .chip').forEach(c => c.addEventListener('click', () => {
    document.querySelectorAll('.chips .chip').forEach(x => x.setAttribute('aria-pressed', String(x === c)));
    S.pos = c.dataset.pos; renderTable();
  }));
  $('rows').addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) openPanel(tr.dataset.id); });
  $('rows').addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('tr[data-id]')) { e.preventDefault(); openPanel(e.target.dataset.id); } });
  $('panelClose').addEventListener('click', () => $('panel').close());
}
function showcaseRep(id) {
  let best = null;
  S.plays.forEach((pl, i) => {
    if (!pl.players.some(x => String(x.nflId) === String(id) && x.side === 'BLOCK')) return;
    const v = Math.max(0, ...pl.frames.map(f => (f.sys || {})[id] || 0));
    if (!best || v > best.v) best = { i, v, pl };
  });
  return best;
}
function openPanel(id) {
  const p = S.lb && S.lb.players.find(x => String(x.nflId) === String(id)); if (!p) return;
  const t = tier(p), d = p.sys25 - p.positionAvg, wk = (p.byWeek || []).slice().sort((a, b) => a.week - b.week), wr = p.worstRep;
  const sc = showcaseRep(p.nflId);
  const idx = wr ? S.plays.findIndex(x => x.meta.gameId === wr.gameId && x.meta.playId === wr.playId) : -1;
  $('panelBody').innerHTML = `
    <p class="eyebrow">${esc(p.team)} · ${esc(p.position)}</p><h2 id="panelTitle">${esc(p.name)}</h2>
    <div class="kpis">
      <div><span class="k">SYS@2.5</span><span class="v">${p.sys25.toFixed(1)}<small> yd²</small></span></div>
      <div><span class="k">${esc(p.position)} avg</span><span class="v">${p.positionAvg.toFixed(1)}<small> yd²</small></span></div>
      <div><span class="k">Percentile</span><span class="v">${Math.round(p.percentile)}</span></div>
      <div><span class="k">Tier</span><span class="v"><span class="grade ${t[0]}">${t[1]}</span></span></div>
    </div>
    <p class="note">${p.snaps} snaps lasting 2.5 s or more · ${d >= 0 ? '+' : ''}${d.toFixed(1)} yd² vs the ${esc(p.position)} average${Number.isFinite(p.pressureRate) ? ` · PFF pressure allowed on ${(p.pressureRate * 100).toFixed(1)}% of those snaps` : ''}</p>
    <h3>SYS by week</h3>${wk.length ? weekChart(wk, p.positionAvg) : '<p class="note">Weekly data unavailable.</p>'}
    <h3>Worst rep</h3>${wr ? `<p>${wr.week ? `Week ${wr.week} · ` : ''}<strong>${wr.sys25.toFixed(1)} yd²</strong> surrendered by 2.5 s</p><p class="note">${esc(wr.description)}</p>${idx >= 0 ? '<button class="btn" id="watch" type="button">Watch this rep</button>' : '<p class="note">Replay not in the showcase set.</p>'}` : '<p class="note">No worst rep recorded.</p>'}
    ${sc && idx < 0 ? `<h3>On the replay</h3><p class="note">${esc(playLabel(sc.pl))} · up to ${sc.v.toFixed(1)} yd² surrendered</p><button class="btn" id="watchSc" type="button">Watch his showcase rep</button>` : ''}`;
  $('panel').showModal();
  if (sc && idx < 0) $('watchSc').addEventListener('click', () => { $('panel').close(); selectPlay(sc.i); $('stage').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth' }); });
  if (idx >= 0) $('watch').addEventListener('click', () => { $('panel').close(); selectPlay(idx); $('stage').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth' }); });
}
function weekChart(wk, avg) {
  const w = 320, h = 120, pad = { l: 28, r: 8, t: 8, b: 20 }, max = Math.max(avg, ...wk.map(x => x.sys25)) * 1.15 || 1;
  const bw = (w - pad.l - pad.r) / 8, sy = v => pad.t + (1 - v / max) * (h - pad.t - pad.b);
  const bars = wk.map(x => `<rect x="${pad.l + (x.week - 1) * bw + 3}" y="${sy(x.sys25)}" width="${bw - 6}" height="${sy(0) - sy(x.sys25)}" style="fill:var(--accent)" rx="2"><title>Week ${x.week}: ${x.sys25.toFixed(1)} yd²${x.snaps ? ` over ${x.snaps} snaps` : ''}</title></rect>`).join('');
  const labels = Array.from({ length: 8 }, (_, i) => `<text x="${pad.l + i * bw + bw / 2}" y="${h - 6}" text-anchor="middle" font-size="10" style="fill:var(--muted)">W${i + 1}</text>`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="SYS at 2.5 seconds by week; dashed line is the position average, ${avg.toFixed(1)} square yards">${bars}<line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(avg)}" y2="${sy(avg)}" style="stroke:var(--bad)" stroke-dasharray="4 3"/><text x="${pad.l - 4}" y="${sy(avg) + 3}" text-anchor="end" font-size="9" style="fill:var(--bad)">avg</text>${labels}</svg>
  <table class="sr-only"><caption>SYS by week</caption><tr><th>Week</th><th>SYS@2.5</th></tr>${wk.map(x => `<tr><td>${x.week}</td><td>${x.sys25.toFixed(1)}</td></tr>`).join('')}</table>`;
}

// ---------- validation section ----------
function renderValidation(v) {
  const ph = v.stub ? '<span class="ph">Placeholder · awaiting Workstream B results</span>' : '';
  $('heads').innerHTML = v.headlines.map(h => `<div class="headline">${ph}<div class="num">${esc(h.value)}${h.unit ? `<small> ${esc(h.unit)}</small>` : ''}</div><div class="lbl">${esc(h.label)}</div>${h.note ? `<p class="note">${esc(h.note)}</p>` : ''}</div>`).join('');
  $('charts').innerHTML = v.charts.map(c => `<figure class="chart">${ph}<figcaption><strong>${esc(c.title)}</strong>${c.caption ? `<br><span class="note">${esc(c.caption)}</span>` : ''}</figcaption>${chartSVG(c)}</figure>`).join('');
}
function chartSVG(c) {
  const pts = c.series.flatMap(s => s.points);
  if (!pts.length) return '<p class="note">No data points yet.</p>';
  const w = 420, h = 220, pad = { l: 44, r: 10, t: 10, b: 40 }, xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(...ys);
  if (c.type === 'bar') { x0 -= 0.5; x1 += 0.5; }
  if (x1 === x0) x1 = x0 + 1; if (y1 === y0) y1 = y0 + 1;
  const sx = v => pad.l + (v - x0) / (x1 - x0) * (w - pad.l - pad.r), sy = v => pad.t + (1 - (v - y0) / (y1 - y0)) * (h - pad.t - pad.b);
  const colors = ['var(--accent)', 'var(--b-lg)', 'var(--b-c)', 'var(--b-rt)', 'var(--b-rg)', 'var(--b-lt)'], n = c.series.length;
  const bw = (w - pad.l - pad.r) / (x1 - x0) * 0.7 / n;
  const body = c.series.map((s, si) => {
    const col = colors[si % colors.length];
    if (c.type === 'bar') return s.points.map(([x, y]) => `<rect x="${sx(x) - bw * n / 2 + si * bw}" y="${Math.min(sy(y), sy(0))}" width="${bw}" height="${Math.abs(sy(0) - sy(y))}" style="fill:${col}"><title>${esc(s.name)}: ${y}</title></rect>`).join('');
    if (c.type === 'line') return `<polyline points="${s.points.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' ')}" fill="none" style="stroke:${col}" stroke-width="2"/>`;
    return s.points.map(([x, y]) => `<circle cx="${sx(x)}" cy="${sy(y)}" r="3.5" style="fill:${col}" fill-opacity=".75"><title>${esc(s.name)}: (${x}, ${y})</title></circle>`).join('');
  }).join('');
  const ticks = Array.isArray(c.xTicks) ? c.xTicks.map((l, i) => `<text x="${sx(i)}" y="${h - pad.b + 14}" text-anchor="middle" font-size="10" style="fill:var(--muted)">${esc(l)}</text>`).join('') : '';
  const legend = n > 1 ? `<text x="${pad.l + 4}" y="${pad.t + 12}" font-size="10" style="fill:var(--fg-2)">${c.series.map((s, si) => `<tspan style="fill:${colors[si % colors.length]}">■</tspan> ${esc(s.name)}  `).join('')}</text>` : '';
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${esc(c.title)}"><desc>${esc(c.caption || `${c.xLabel} against ${c.yLabel}`)}</desc>
    <line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(y0)}" y2="${sy(y0)}" style="stroke:var(--line)"/><line x1="${pad.l}" x2="${pad.l}" y1="${pad.t}" y2="${sy(y0)}" style="stroke:var(--line)"/>
    <text x="${pad.l - 6}" y="${sy(y1) + 4}" text-anchor="end" font-size="10" style="fill:var(--muted)">${+y1.toFixed(2)}</text>
    <text x="${pad.l - 6}" y="${sy(y0) + 4}" text-anchor="end" font-size="10" style="fill:var(--muted)">${+y0.toFixed(2)}</text>
    ${body}${ticks}${legend}
    <text x="${(pad.l + w - pad.r) / 2}" y="${h - 4}" text-anchor="middle" font-size="11" style="fill:var(--fg-2)">${esc(c.xLabel)}</text>
    <text x="12" y="${(pad.t + h - pad.b) / 2}" text-anchor="middle" font-size="11" style="fill:var(--fg-2)" transform="rotate(-90 12 ${(pad.t + h - pad.b) / 2})">${esc(c.yLabel)}</text></svg>`;
}

// ---------- audience angles, theme ----------
function setupAngles() {
  $('goCoach').addEventListener('click', () => {
    const rows = displayed(); $('season').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth' });
    if (!rows.length) { $('coachMsg').textContent = 'No linemen to open yet.'; return; }
    const withRep = rows.filter(p => showcaseRep(p.nflId)), pool = withRep.length ? withRep : rows;
    openPanel(pool.reduce((a, b) => (b.sys25 - b.positionAvg > a.sys25 - a.positionAvg ? b : a)).nflId);
  });
  $('goScout').addEventListener('click', () => { $('season').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth' }); $('search').focus({ preventScroll: true }); });
  $('goBroadcast').addEventListener('click', () => { setBroadcast(true); $('stage').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth' }); if (S.tl && !S.playing) { set(0); toggle(); } });
  $('bcast').addEventListener('click', () => setBroadcast(!S.bcast));
  $('play').addEventListener('click', toggle);
  $('t').addEventListener('input', () => { stop(); set(+$('t').value); });
}
function setupTheme() {
  const btn = $('theme'), mq = matchMedia('(prefers-color-scheme: dark)');
  const cur = () => document.documentElement.dataset.theme || (mq.matches ? 'dark' : 'light');
  const label = () => { const next = cur() === 'dark' ? 'light' : 'dark'; btn.textContent = next === 'dark' ? 'Dark mode' : 'Light mode'; btn.setAttribute('aria-label', `Switch to ${next} mode`); };
  const redraw = () => { label(); draw(); if (S.lb) renderTable(); };
  btn.addEventListener('click', () => { document.documentElement.dataset.theme = cur() === 'dark' ? 'light' : 'dark'; redraw(); });
  mq.addEventListener('change', redraw);
  label();
}
function updateTag() {
  const any = stub.replays || stub.leaderboard || stub.validation, tag = $('dataTag');
  tag.hidden = !any;
  tag.textContent = any ? 'Work in progress · some sections show placeholder data' : '';
}

async function init() {
  setupCanvas(); setupLeaderboardUI(); setupAngles(); setupTheme();
  document.fonts?.ready.then(() => draw());
  const [rp, lb, va] = await Promise.allSettled(['replays.json', 'leaderboard.json', 'validation.json'].map(loadJSON));
  if (rp.status === 'rejected') { fail($('replayErr'), 'replays.json', [rp.reason.message]); $('sit').textContent = 'No plays available'; }
  else {
    const errs = validateReplays(rp.value);
    if (errs.length) { fail($('replayErr'), 'replays.json', errs); $('sit').textContent = 'No plays available'; }
    else { S.plays = rp.value; stub.replays = S.plays.every(p => p.meta.synthetic); setupPicker(); }
  }
  if (lb.status === 'rejected') { fail($('lbErr'), 'leaderboard.json', [lb.reason.message]); $('rows').innerHTML = ''; }
  else {
    const errs = validateLeaderboard(lb.value);
    if (errs.length) { fail($('lbErr'), 'leaderboard.json', errs); $('rows').innerHTML = ''; }
    else {
      S.lb = lb.value; stub.leaderboard = lb.value.stub !== false && lb.value.stub !== undefined;
      $('lbNote').textContent = `Average yd² charged per pass-block snap at the 2.5-second mark (plays lasting 2.5 s or more). Lower is better. Min. ${lb.value.minSnaps ?? 150} snaps. Tiers: top quarter at the position is Wall, bottom quarter Leaky.${lb.value.source ? ' ' + lb.value.source : ''}`;
      renderTable();
    }
  }
  if (va.status === 'rejected') fail($('valErr'), 'validation.json', [va.reason.message]);
  else {
    const errs = validateValidation(va.value);
    if (errs.length) fail($('valErr'), 'validation.json', errs);
    else { stub.validation = va.value.stub !== false && va.value.stub !== undefined; renderValidation(va.value); }
  }
  updateTag();
}
init();
