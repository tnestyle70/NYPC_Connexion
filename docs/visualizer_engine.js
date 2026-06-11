// =============================================================================
// Connexion 규칙 엔진 + 사다리 봇 JS 포트 — 브라우저(visualizer.html) / Node 공용
// 진실원: src/core.hpp (C++). 이 파일은 "보는 용도"의 미러이며,
// scripts/visualizer_engine_test.js 가 골든(24/20) + 사이트 로그(196/304) +
// s1 섀도(32/32)로 C++와 동일 동작임을 핀 고정한다.
// =============================================================================
(function (global) {
  "use strict";

  const COLS = "abcdef";
  const HOLES = new Set(["a1-", "a4-", "c3+", "c6+", "d1-", "d4-", "f3+", "f6+"]);

  const CELLS = []; // 압축 id 순서 = 열 a..f × 행 1..6 × −,+ (C++ colmajor와 동일)
  for (const c of COLS) for (let r = 1; r <= 6; r++) for (const s of "-+") {
    const n = c + r + s;
    if (!HOLES.has(n)) CELLS.push(n);
  }
  const CELL_ID = {};
  CELLS.forEach((n, i) => { CELL_ID[n] = i; });

  const ROWMAJOR = []; // s1(사이트 봇) 순회 순서: 행 1→6 × 열 a→f × −,+
  for (let r = 1; r <= 6; r++) for (const c of COLS) for (const s of "-+") {
    const n = c + r + s;
    if (!HOLES.has(n)) ROWMAJOR.push(n);
  }

  const COLORS = "RGBY";
  const TYPES = []; // type id 순서 = 색 R,G,B,Y × 문양 1..4
  for (const c of COLORS) for (let p = 1; p <= 4; p++) TYPES.push(c + p);
  const TYPE_IDX = {};
  TYPES.forEach((t, i) => { TYPE_IDX[t] = i; });

  function neighborsOf(name) {
    const col = COLS.indexOf(name[0]);
    const row = +name[1];
    const s = name[2];
    const cand = s === "-"
      ? [[col, row, "+"], [col - 1, row, "+"], [col, row - 1, "+"]]
      : [[col, row, "-"], [col + 1, row, "-"], [col, row + 1, "-"]];
    const out = [];
    for (const [c, r, sg] of cand) {
      if (c < 0 || c > 5 || r < 1 || r > 6) continue;
      const n = COLS[c] + r + sg;
      if (!HOLES.has(n)) out.push(n);
    }
    return out;
  }
  const NEIGH = {};
  CELLS.forEach((n) => { NEIGH[n] = neighborsOf(n); });

  // --- 라이브 모드 RNG (referee 시드와 별개 체계 — 재현은 리플레이 모드로) ---
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffled(arr, rnd) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  function fullBag() { // 한 플레이어 주머니 = 16종 × 2장 (docs/GAME_RULES.md 판정)
    const b = [];
    for (const t of TYPES) { b.push(t, t); }
    return b;
  }

  // --- 롤백 union-find (C++ GroupSet 포트): Σ(성분 크기)² 증분 유지 ---
  class Dsu {
    constructor() {
      this.parent = new Int8Array(64).fill(-1);
      this.size = new Int8Array(64);
      this.sumSq = 0;
      this.ops = [];
    }
    find(x) { while (this.parent[x] !== x) x = this.parent[x]; return x; }
    activate(c) { this.parent[c] = c; this.size[c] = 1; this.sumSq += 1; }
    link(a, b) {
      let ra = this.find(a), rb = this.find(b);
      if (ra === rb) return;
      if (this.size[ra] < this.size[rb]) { const t = ra; ra = rb; rb = t; }
      const sa = this.size[ra], sb = this.size[rb];
      this.sumSq += (sa + sb) * (sa + sb) - sa * sa - sb * sb;
      this.parent[rb] = ra;
      this.size[ra] = sa + sb;
      this.ops.push([ra, rb]);
    }
    rollback(mark, cell) {
      while (this.ops.length > mark) {
        const [into, from] = this.ops.pop();
        const s = this.size[into], sb = this.size[from], sa = s - sb;
        this.sumSq += sa * sa + sb * sb - s * s;
        this.size[into] = sa;
        this.parent[from] = from;
      }
      this.parent[cell] = -1;
      this.size[cell] = 0;
      this.sumSq -= 1;
    }
  }

  // --- 게임 상태 ---
  class Game {
    constructor() { this.reset(); }
    reset() {
      this.board = new Array(64).fill(null); // 타일 문자열 or null
      this.pat = new Dsu();
      this.col = new Dsu();
      this.hands = [[], []]; // 도착 순서 배열 (양측 공개)
      this.bags = [[], []];
      this.ply = 0;
    }
    setupLive(seed) { // 각자 주머니 16종×2장 셔플, 5장 드로우
      this.reset();
      const rnd = mulberry32(seed);
      for (let p = 0; p < 2; p++) this.bags[p] = shuffled(fullBag(), rnd);
      for (let p = 0; p < 2; p++) for (let i = 0; i < 5; i++) this.hands[p].push(this.bags[p].pop());
    }
    setupReplay(hands0) { // 리플레이: 손패만 세팅, 드로우는 기록을 따름
      this.reset();
      this.hands[0] = hands0[0].slice();
      this.hands[1] = hands0[1].slice();
    }
    toMove() { return this.ply & 1; }
    patScore() { return this.pat.sumSq; }   // 선공(문양) 점수
    colScore() { return this.col.sumSq; }   // 후공(색) 점수
    margin(seat) { // seat 시점 점수차
      const m = this.pat.sumSq - this.col.sumSq;
      return seat === 0 ? m : -m;
    }
    place(seat, cellName, tile) {
      const id = CELL_ID[cellName];
      const mark = { id, tile, seat, markP: this.pat.ops.length, markC: this.col.ops.length,
                     handIndex: this.hands[seat].indexOf(tile) };
      this.board[id] = tile;
      if (mark.handIndex >= 0) this.hands[seat].splice(mark.handIndex, 1);
      this.pat.activate(id);
      this.col.activate(id);
      for (const nb of NEIGH[cellName]) {
        const nt = this.board[CELL_ID[nb]];
        if (!nt) continue;
        if (nt[1] === tile[1]) this.pat.link(id, CELL_ID[nb]);
        if (nt[0] === tile[0]) this.col.link(id, CELL_ID[nb]);
      }
      this.ply++;
      return mark;
    }
    unplace(mark) {
      this.ply--;
      this.pat.rollback(mark.markP, mark.id);
      this.col.rollback(mark.markC, mark.id);
      if (mark.handIndex >= 0) this.hands[mark.seat].splice(mark.handIndex, 0, mark.tile);
      this.board[mark.id] = null;
    }
    // 무변이 1수 델타: 이웃 루트 집합 수학으로 Δ문양/Δ색 동시 계산
    placeDelta(cellName, tile) {
      const calc = (dsu, attrIdx) => {
        const roots = new Set();
        let s = 1, sub = 0;
        for (const nb of NEIGH[cellName]) {
          const nt = this.board[CELL_ID[nb]];
          if (!nt || nt[attrIdx] !== tile[attrIdx]) continue;
          const r = dsu.find(CELL_ID[nb]);
          if (!roots.has(r)) {
            roots.add(r);
            s += dsu.size[r];
            sub += dsu.size[r] * dsu.size[r];
          }
        }
        return s * s - sub;
      };
      return { dPat: calc(this.pat, 1), dCol: calc(this.col, 0) };
    }
    distinctTypes(seat) { // type id 오름차순
      const have = new Set(this.hands[seat]);
      return TYPES.filter((t) => have.has(t));
    }
    emptyCells(order) {
      const o = order || CELLS;
      return o.filter((c) => !this.board[CELL_ID[c]]);
    }
  }

  // --- 사다리 봇 (src/bots.hpp 동률 해소까지 포트) ---
  function marginD(g, seat, cell, tile) {
    const { dPat, dCol } = g.placeDelta(cell, tile);
    return seat === 0 ? dPat - dCol : dCol - dPat;
  }

  const bots = {
    // c1: 최소 type 손패 → 최소 id 빈칸
    c1(g, seat) {
      const t = g.distinctTypes(seat)[0];
      const cell = g.emptyCells()[0];
      return { cell, tile: t };
    },
    // c2: 자기 점수 최대 — 공식 예제 순회 (타일=손패 도착순 outer × 칸 id asc inner, strict >)
    c2(g, seat) {
      let best = -Infinity, mv = null;
      for (const t of g.hands[seat]) {
        for (const cell of CELLS) {
          if (g.board[CELL_ID[cell]]) continue;
          const { dPat, dCol } = g.placeDelta(cell, t);
          const v = seat === 0 ? dPat : dCol;
          if (v > best) { best = v; mv = { cell, tile: t }; }
        }
      }
      return mv;
    },
    // c3: 마진 그리디 (칸 id asc outer × type id asc inner, strict >)
    c3(g, seat) {
      let best = -Infinity, mv = null;
      const types = g.distinctTypes(seat);
      for (const cell of CELLS) {
        if (g.board[CELL_ID[cell]]) continue;
        for (const t of types) {
          const v = marginD(g, seat, cell, t);
          if (v > best) { best = v; mv = { cell, tile: t }; }
        }
      }
      return mv;
    },
    // s1: 사이트 샘플 AI 레플리카 — 마진 그리디, 칸 outer(행우선) × 손패 도착순 inner, strict >
    s1(g, seat) {
      let best = -Infinity, mv = null;
      for (const cell of ROWMAJOR) {
        if (g.board[CELL_ID[cell]]) continue;
        for (const t of g.hands[seat]) {
          const v = marginD(g, seat, cell, t);
          if (v > best) { best = v; mv = { cell, tile: t }; }
        }
      }
      return mv;
    },
    // c4: minimax d0 — 내 수 + 상대 최선 정적 응수 (중간 방어)
    c4(g, seat) {
      const cands = [];
      const types = g.distinctTypes(seat);
      for (const cell of CELLS) {
        if (g.board[CELL_ID[cell]]) continue;
        for (const t of types) {
          cands.push({ cell, t, d: marginD(g, seat, cell, t), ci: CELL_ID[cell], ti: TYPE_IDX[t] });
        }
      }
      cands.sort((a, b) => b.d - a.d || a.ci - b.ci || a.ti - b.ti);
      let best = -Infinity, mv = null;
      const opp = 1 - seat;
      for (const c of cands) {
        const mark = g.place(seat, c.cell, c.t);
        const V = g.margin(seat);
        let worst = Infinity, any = false;
        const otypes = g.distinctTypes(opp);
        for (const cell2 of CELLS) {
          if (g.board[CELL_ID[cell2]]) continue;
          for (const t2 of otypes) {
            any = true;
            const v2 = V + marginD(g, seat, cell2, t2); // 상대 수가 내 마진에 주는 변화
            if (v2 < worst) worst = v2;
          }
        }
        const val = any ? worst : V;
        g.unplace(mark);
        if (val > best) { best = val; mv = { cell: c.cell, tile: c.t }; }
      }
      return mv;
    },
  };

  // --- 로그 파서 ---
  // 웹사이트 리플레이: INIT 10장 / FIRST|SECOND cell tile drawn t / SCOREFIRST n / SCORESECOND n
  function parseSiteLog(text) {
    let hands0 = null;
    const moves = [];
    const scores = {};
    for (const line of text.split(/\r?\n/)) {
      const t = line.trim().split(/\s+/);
      if (!t[0]) continue;
      if (t[0] === "INIT") hands0 = [t.slice(1, 6), t.slice(6, 11)];
      else if (t[0] === "FIRST" || t[0] === "SECOND") {
        moves.push({ seat: t[0] === "FIRST" ? 0 : 1, cell: t[1], tile: t[2], draw: t[3] });
      } else if (t[0] === "SCOREFIRST") scores.first = +t[1];
      else if (t[0] === "SCORESECOND") scores.second = +t[1];
    }
    return { hands0, moves, scores };
  }
  // referee.py JSONL 한 줄 (hands0 필드 포함 버전)
  function parseRefereeJson(text) {
    const r = JSON.parse(text.trim());
    return {
      hands0: r.hands0 || null,
      moves: (r.moves || []).map((m) => ({ seat: m.seat, cell: m.cell, tile: m.tile, draw: m.draw })),
      scores: { first: r.score_first, second: r.score_second },
    };
  }
  function parseAnyLog(text) {
    const s = text.trim();
    if (s.startsWith("{")) return parseRefereeJson(s.split(/\r?\n/)[0]);
    return parseSiteLog(s);
  }

  // --- 골든 자가검증 (finals_1 예시 보드: 선공 24 / 후공 20) ---
  function goldenSelfTest() {
    const fails = [];
    const eq = (a, b, msg) => { if (JSON.stringify(a) !== JSON.stringify(b)) fails.push(msg); };
    eq(CELLS.length, 64, "64칸");
    eq(NEIGH["c5-"].slice().sort(), ["b5+", "c4+", "c5+"], "neigh(c5-)");
    eq(NEIGH["f4+"].slice().sort(), ["f4-", "f5-"], "neigh(f4+)");
    const g = new Game();
    g.hands = [[], []];
    const seq = [["a4+", "G2"], ["a5-", "G1"], ["b4-", "B2"], ["b4+", "Y2"], ["b5-", "Y4"],
                 ["b5+", "R4"], ["b6-", "B4"], ["c4+", "R3"], ["c5-", "R2"], ["c5+", "Y2"]];
    const marks = [];
    seq.forEach(([cell, tile], i) => {
      g.hands[i & 1].push(tile);
      marks.push(g.place(i & 1, cell, tile));
    });
    eq(g.patScore(), 24, "골든 선공(문양) 24");
    eq(g.colScore(), 20, "골든 후공(색) 20");
    for (let i = 9; i >= 0; i--) g.unplace(marks[i]);
    eq(g.pat.sumSq + g.col.sumSq, 0, "롤백 0");
    return { ok: fails.length === 0, fails };
  }

  const CX = {
    COLS, HOLES, CELLS, CELL_ID, ROWMAJOR, COLORS, TYPES, TYPE_IDX, NEIGH,
    mulberry32, shuffled, fullBag, Dsu, Game, bots,
    parseSiteLog, parseRefereeJson, parseAnyLog, goldenSelfTest,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = CX;
  else global.CX = CX;
})(typeof window !== "undefined" ? window : globalThis);
