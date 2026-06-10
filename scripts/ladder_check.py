#!/usr/bin/env python3
"""G3(사다리 단조성) + G4(결정론) 게이트.

- G4: 동일 매치업/시드 2회 → 수순(JSON) 완전 동일.
- G3: 인접 티어 (c1,c2)...(c6,c7) 시드 배터리 × 선후공 → 상위 티어 승률 리포트.
      기본은 리포트 모드 (--strict 시 임계 미달이면 exit 1). 타이밍(최대 수당 ms)도 함께 보고.

사용 (WSL): python3 scripts/ladder_check.py --exe build/sample_ai --seeds 2
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from referee import LADDER_TIERS, play_game, points  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="build/sample_ai")
    ap.add_argument("--seeds", type=int, default=2, help="티어쌍당 시드 수 (x 선후 2판)")
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    bot = lambda t: f"{args.exe} {t}"  # noqa: E731
    fails = 0

    # --- G4 결정론 ---
    r1 = play_game(bot("c4"), bot("c3"), seed=args.seed_base)
    r2 = play_game(bot("c4"), bot("c3"), seed=args.seed_base)
    m1 = [(m["cell"], m["tile"], m["draw"]) for m in r1["moves"]]
    m2 = [(m["cell"], m["tile"], m["draw"]) for m in r2["moves"]]
    if m1 == m2 and len(m1) == 64:
        print(f"G4 PASS: 동일 시드 2회 = 동일 수순 (64수, score {r1['score_first']}:{r1['score_second']})")
    else:
        print(f"G4 FAIL: 수순 불일치 또는 미완주 (len {len(m1)}/{len(m2)})")
        fails += 1

    # --- G3 단조성 ---
    print(f"G3 인접 티어 승률 (시드 {args.seeds}개 × 선후 2판, 임계 {args.threshold}):")
    seed = args.seed_base + 10
    max_ms = {t: 0 for t in LADDER_TIERS}
    for lo, hi in zip(LADDER_TIERS, LADDER_TIERS[1:]):
        pts_hi = 0.0
        n = 0
        for s in range(args.seeds):
            for hi_first in (True, False):
                cf, cs = (bot(hi), bot(lo)) if hi_first else (bot(lo), bot(hi))
                r = play_game(cf, cs, seed)
                seed += 1
                if r["fault"]:
                    print(f"  ! fault in {lo} vs {hi}: {r['fault']}")
                pts_hi += points(r, 0 if hi_first else 1)
                n += 1
                f_t, s_t = (hi, lo) if hi_first else (lo, hi)
                max_ms[f_t] = max(max_ms[f_t], r["max_move_ms"][0])
                max_ms[s_t] = max(max_ms[s_t], r["max_move_ms"][1])
        rate = pts_hi / n
        mark = "ok" if rate >= args.threshold else "LOW"
        print(f"  {hi} vs {lo}: {pts_hi}/{n} = {rate:.2f}  [{mark}]")
        if rate < args.threshold:
            fails += 0 if not args.strict else 1

    print("타이밍 (최대 수당 ms): " + ", ".join(f"{t}={max_ms[t]}" for t in LADDER_TIERS))
    over = [t for t in LADDER_TIERS if max_ms[t] > 800]
    if over:
        print(f"주의: 수당 800ms 초과 티어 {over} — 폭 상수 축소 검토 (10초 총시계)")

    if args.strict and fails:
        print(f"STRICT FAIL: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
