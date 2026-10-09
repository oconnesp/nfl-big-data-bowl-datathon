import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { readFileSync } from 'node:fs';
import { computeTimeline, FULL } from '../src/engine.js';
import { validateReplays, validateLeaderboard, validateValidation } from '../src/validate.js';

const read = f => JSON.parse(readFileSync(new URL(`../public/data/${f}`, import.meta.url), 'utf8'));
const plays = read('replays.json');

describe('mockup parity', () => {
  it('reproduces the mockup sack-frame numbers within 10%', () => {
    const p = plays.find(x => x.meta.synthetic);
    const tl = computeTimeline(p), last = tl.frames.at(-1);
    const id = slot => String(p.players.find(x => x.lined_up === slot).nflId);
    const near = (v, target) => expect(Math.abs(v - target) / target).toBeLessThan(0.1);
    near(last.sys[id('RT')], 31.1); near(last.sys[id('LG')], 7.4);
    near(tl.frames[0].pocket, 63); near(last.pocket, 21);
  });
});

describe('agreement with the Workstream A pipeline', () => {
  it('matches the precomputed per-frame SYS and pocket on real plays', () => {
    const diffs = [];
    for (const p of plays.filter(x => !x.meta.synthetic)) {
      const tl = computeTimeline(p);
      p.frames.forEach((f, k) => {
        for (const [id, v] of Object.entries(f.sys || {})) diffs.push(Math.abs((tl.frames[k].sys[id] ?? 0) - v));
        if (f.pocket != null) diffs.push(Math.abs(tl.frames[k].pocket - f.pocket));
      });
    }
    expect(Math.max(0, ...diffs)).toBeLessThanOrEqual(0.5);
  });
});

const pt = fc.tuple(fc.double({ min: -10, max: 10, noNaN: true }), fc.double({ min: -12, max: 3, noNaN: true }));
const playArb = fc.record({ nB: fc.integer({ min: 1, max: 5 }), nR: fc.integer({ min: 1, max: 6 }), nF: fc.integer({ min: 1, max: 5 }) })
  .chain(({ nB, nR, nF }) => fc.record({
    assign: fc.array(fc.subarray([...Array(nB).keys()]), { minLength: nR, maxLength: nR }),
    frames: fc.array(fc.array(pt, { minLength: 1 + nB + nR, maxLength: 1 + nB + nR }), { minLength: nF, maxLength: nF }),
  }).map(({ assign, frames }) => {
    const players = [{ nflId: 1, side: 'QB' }, ...Array.from({ length: nB }, (_, i) => ({ nflId: 100 + i, side: 'BLOCK' })), ...Array.from({ length: nR }, (_, i) => ({ nflId: 200 + i, side: 'RUSH' }))];
    return {
      meta: { gameId: 1, playId: 1 }, players,
      assign: Object.fromEntries(assign.map((bs, k) => [String(200 + k), bs.map(b => String(100 + b))])),
      frames: frames.map((ps, j) => ({ t: j / 10, pos: Object.fromEntries(players.map((p, i) => [String(p.nflId), ps[i]])) })),
    };
  }));

describe('SYS engine properties', () => {
  it('conserves charged area, stays non-negative and bounded, charges nothing at the snap, and is deterministic', () => {
    fc.assert(fc.property(playArb, play => {
      const tl = computeTimeline(play);
      tl.frames.forEach((fr, k) => {
        const sumSys = Object.values(fr.sys).reduce((a, b) => a + b, 0), sumCh = fr.charged.reduce((a, b) => a + b, 0);
        expect(Math.abs(sumSys - sumCh)).toBeLessThan(1e-9);
        for (const v of Object.values(fr.sys)) expect(v).toBeGreaterThanOrEqual(0);
        expect(fr.pocket).toBeGreaterThanOrEqual(-1e-9); expect(fr.pocket).toBeLessThanOrEqual(FULL + 1e-9);
        if (k === 0) expect(sumCh).toBe(0);
        tl.by.forEach((ids, r) => { if (!ids.length) return; for (const id of ids) expect(fr.sys[id]).toBeGreaterThanOrEqual(fr.charged[r] / ids.length - 1e-9); });
      });
      expect(computeTimeline(play).frames.map(f => f.sys)).toEqual(tl.frames.map(f => f.sys));
      expect(validateReplays([JSON.parse(JSON.stringify(play))])).toEqual([]);
    }), { numRuns: 100 });
  });
});

describe('validators', () => {
  it('accept the shipped data files', () => {
    expect(validateReplays(plays)).toEqual([]);
    expect(validateLeaderboard(read('leaderboard.json'))).toEqual([]);
    expect(validateValidation(read('validation.json'))).toEqual([]);
  });
  it('reject malformed plays with JSON paths', () => {
    const p = structuredClone(plays[0]);
    p.players.push({ ...p.players.find(x => x.side === 'QB'), nflId: 1 });
    p.assign['999'] = ['12345'];
    p.frames[3].t = p.frames[2].t;
    const errs = validateReplays([p]);
    expect(errs.some(e => e.startsWith('$[0].players') && e.includes('exactly 1 QB'))).toBe(true);
    expect(errs.some(e => e.startsWith('$[0].frames[3].t'))).toBe(true);
    expect(errs.some(e => e.startsWith('$[0].assign.999'))).toBe(true);
    expect(errs.some(e => e.includes('.pos.1'))).toBe(true);
    expect(validateReplays({})).toEqual(['$: expected an array of plays']);
  });
});
