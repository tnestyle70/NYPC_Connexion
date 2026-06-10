#!/usr/bin/env python3
"""G2 골든 테스트 — 토폴로지 + finals_1 예시 보드(선공 24/후공 20).

파이썬 규칙 미러(connexion_rules.py)를 검증하고, --exe 가 주어지면 C++ 쪽
`sample_ai --selftest` 도 함께 실행해 양쪽 구현을 같은 골든으로 핀 고정한다.

사용 (WSL): python3 scripts/golden_test.py --exe build/sample_ai
"""

import argparse
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connexion_rules import CELLS, NEIGH, REMOVED, component_sq_sum, score  # noqa: E402

FAILS = 0


def check(cond, msg):
    global FAILS
    if not cond:
        print(f"FAIL: {msg}")
        FAILS += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", help="C++ sample_ai 바이너리 (옵션, --selftest 호출)")
    args = ap.parse_args()

    # --- 토폴로지 ---
    check(len(CELLS) == 64, "64 cells")
    check(all(r not in CELLS for r in REMOVED), "8 removed cells absent")
    check(sorted(NEIGH["c5-"]) == ["b5+", "c4+", "c5+"], "neigh(c5-)")
    check(sorted(NEIGH["f4+"]) == ["f4-", "f5-"], "neigh(f4+)")
    check(sorted(NEIGH["a4+"]) == ["a5-", "b4-"], "neigh(a4+) — a4- 미사용")
    for c in CELLS:
        check(1 <= len(NEIGH[c]) <= 3, f"neighbor count {c}")
        for n in NEIGH[c]:
            check(c in NEIGH[n], f"symmetry {c}~{n}")

    # --- 골든 보드 (finals_1 점수 계산 예시) ---
    board = {
        "a4+": "G2", "a5-": "G1", "b4-": "B2", "b4+": "Y2", "b5-": "Y4",
        "b5+": "R4", "b6-": "B4", "c4+": "R3", "c5-": "R2", "c5+": "Y2",
    }
    sf, ss = score(board)
    check(sf == 24, f"선공(문양) 24 (got {sf})")
    check(ss == 20, f"후공(색) 20 (got {ss})")
    # 성분 구조 세부 (문양: 3,2,1,3,1 / 색: 3,2,1,2,1,1)
    check(component_sq_sum(board, 1) == 9 + 4 + 1 + 9 + 1, "pattern components 3,2,1,3,1")
    check(component_sq_sum(board, 0) == 9 + 4 + 1 + 4 + 1 + 1, "color components 3,2,1,2,1,1")

    # --- C++ 셀프테스트 ---
    if args.exe:
        r = subprocess.run([args.exe, "--selftest"], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.stderr.strip():
            print(r.stderr.strip())
        check(r.returncode == 0, "C++ --selftest")

    if FAILS == 0:
        print("GOLDEN PASS (python rules" + (" + C++ selftest" if args.exe else "") + ")")
        return 0
    print(f"GOLDEN FAIL: {FAILS} case(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
