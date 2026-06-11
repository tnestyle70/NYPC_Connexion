#!/usr/bin/env node
// JS 엔진(docs/visualizer_engine.js)을 C++/사이트와 핀 고정하는 검증.
// 1) 골든 24/20  2) 사이트 로그 리플레이 196/304  3) s1 섀도 32/32 (c3=7, c2=5 대조)
// 4) 라이브 스모크: c4 vs s1 64수 완주 + 동일 시드 결정론
// 사용: node scripts/visualizer_engine_test.js
"use strict";
const fs = require("fs");
const path = require("path");
const CX = require(path.join(__dirname, "..", "docs", "visualizer_engine.js"));

let fails = 0;
const check = (ok, msg) => {
  console.log((ok ? "PASS" : "FAIL") + "  " + msg);
  if (!ok) fails++;
};

// 1) 골든
const g0 = CX.goldenSelfTest();
check(g0.ok, "골든 자가검증 (24/20 + 토폴로지 + 롤백)" + (g0.ok ? "" : " :: " + g0.fails.join(", ")));

// 2) 사이트 로그 리플레이
const logPath = path.join(__dirname, "..", "Log", "WebSiteBot",
  "2026-06-11_sampleai_p1human_196-304.log");
const rec = CX.parseSiteLog(fs.readFileSync(logPath, "utf-8"));
check(rec.hands0 && rec.moves.length === 64, `로그 파싱: 64수 (${rec.moves.length})`);

function replay(shadowSeat, botName) {
  // C++ shadow_pass 와 동일 의미의 비교: 상태는 기록을 따르고,
  // prefix = 첫 불일치 전까지 일치 수, firstMm = 첫 불일치 시점의 예측.
  const g = new CX.Game();
  g.setupReplay(rec.hands0);
  let prefix = 0, total = 0, firstMm = null;
  for (const m of rec.moves) {
    if (botName && m.seat === shadowSeat) {
      total++;
      const pred = CX.bots[botName](g, shadowSeat);
      const hit = pred && pred.cell === m.cell && pred.tile === m.tile;
      if (hit && !firstMm) prefix++;
      else if (!hit && !firstMm) firstMm = { nth: total, pred };
    }
    g.place(m.seat, m.cell, m.tile);
    if (m.draw !== "X0") g.hands[m.seat].push(m.draw);
  }
  return { pat: g.patScore(), col: g.colScore(), prefix, total, firstMm };
}

const r = replay(-1, null);
check(r.pat === 196 && r.col === 304, `리플레이 점수 재현: ${r.pat}/${r.col} (기대 196/304)`);

// 3) 섀도 (C++ shadow_replay 측정과 동일 불변량으로 핀 고정)
//    s1: 32/32 / c3: prefix 7, 첫 불일치 8번째 수 예측 R2@a4+ / c2: prefix 5, 6번째 B4@b3-
const s1 = replay(1, "s1");
check(s1.prefix === 32 && !s1.firstMm, `s1 섀도: ${s1.prefix}/32 (사이트 봇 레플리카)`);
const c3 = replay(1, "c3");
check(c3.prefix === 7 && c3.firstMm && c3.firstMm.nth === 8 &&
      c3.firstMm.pred.cell === "a4+" && c3.firstMm.pred.tile === "R2",
      `c3 대조: prefix ${c3.prefix}, 첫 불일치 ${c3.firstMm && c3.firstMm.nth}번째 ` +
      `${c3.firstMm && c3.firstMm.pred.tile}@${c3.firstMm && c3.firstMm.pred.cell} (C++: 7, 8번째 R2@a4+)`);
const c2 = replay(1, "c2");
check(c2.prefix === 5 && c2.firstMm && c2.firstMm.nth === 6 &&
      c2.firstMm.pred.cell === "b3-" && c2.firstMm.pred.tile === "B4",
      `c2 대조: prefix ${c2.prefix}, 첫 불일치 ${c2.firstMm && c2.firstMm.nth}번째 ` +
      `${c2.firstMm && c2.firstMm.pred.tile}@${c2.firstMm && c2.firstMm.pred.cell} (C++: 5, 6번째 B4@b3-)`);

// 4) 라이브 스모크 + 결정론
function liveGame(seed, botA, botB) {
  const g = new CX.Game();
  g.setupLive(seed);
  const moves = [];
  for (let ply = 0; ply < 64; ply++) {
    const seat = ply & 1;
    const bot = seat === 0 ? botA : botB;
    const mv = CX.bots[bot](g, seat);
    if (!mv) return null;
    g.place(seat, mv.cell, mv.tile);
    const d = g.bags[seat].length ? g.bags[seat].pop() : null;
    if (d) g.hands[seat].push(d);
    moves.push(mv.cell + mv.tile + (d || "X0"));
  }
  return { moves, pat: g.patScore(), col: g.colScore() };
}
const a1 = liveGame(42, "c4", "s1");
const a2 = liveGame(42, "c4", "s1");
check(a1 && a1.moves.length === 64, `라이브 c4 vs s1 64수 완주 (${a1 ? a1.pat + ":" + a1.col : "실패"})`);
check(JSON.stringify(a1.moves) === JSON.stringify(a2.moves), "동일 시드 2회 = 동일 수순 (결정론)");

const t0 = Date.now();
liveGame(7, "c4", "c4");
console.log(`INFO  c4 vs c4 한 판 소요: ${Date.now() - t0}ms`);

console.log(fails === 0 ? "\nALL PASS" : `\n${fails} FAIL`);
process.exit(fails === 0 ? 0 : 1);
