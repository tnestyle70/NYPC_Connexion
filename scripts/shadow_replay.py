#!/usr/bin/env python3
"""P0 마무리 — 사이트 봇 정체 확정 (섀도 재생, 버섯 lab verify_logs 방법론).

웹사이트 리플레이 로그의 입력 스트림을 지정 시트 관점으로 우리 봇 바이너리에 복제 공급:
  (a) 정확 일치율 — 타이브레이크까지 동일한 정책인가 (C++ 섀도, 첫 불일치에서 중단)
  (b) 1-ply 마진 그리디 argmax 집합 멤버십 — 정책 클래스가 같은가 (python, 전 수 측정)

사용 (WSL):
  python3 scripts/shadow_replay.py Log/WebSiteBot/2026-06-11_sampleai_p1human_196-304.log \
      --seat SECOND --bot "build/sample_ai c3" --bot "build/sample_ai c2"
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connexion_rules import CELLS, component_sq_sum  # noqa: E402
from recover_rules import parse_log  # noqa: E402
from referee import Proc  # noqa: E402


def policy_class_pass(moves, init, seat):
    """seat의 모든 수에 대해 1-ply 마진 그리디 argmax 집합 멤버십을 측정."""
    hands = {"FIRST": list(init[:5]), "SECOND": list(init[5:])}
    board = {}
    my_idx, opp_idx = (1, 0) if seat == "FIRST" else (0, 1)
    total = members = ties = 0
    misses = []
    for side, cell, placed, drawn, _ in moves:
        if side == seat:
            total += 1
            base_my = component_sq_sum(board, my_idx)
            base_opp = component_sq_sum(board, opp_idx)
            best, amax = None, set()
            for t in sorted(set(hands[side])):
                for c in CELLS:
                    if c in board:
                        continue
                    board[c] = t
                    val = (component_sq_sum(board, my_idx) - base_my) - (
                        component_sq_sum(board, opp_idx) - base_opp
                    )
                    del board[c]
                    if best is None or val > best:
                        best, amax = val, {(t, c)}
                    elif val == best:
                        amax.add((t, c))
            if (placed, cell) in amax:
                members += 1
            else:
                misses.append((total, placed, cell, best))
            if len(amax) > 1:
                ties += 1
        board[cell] = placed
        hands[side].remove(placed)
        if drawn != "X0":
            hands[side].append(drawn)
    return total, members, ties, misses


def shadow_pass(moves, init, seat, bot_cmd):
    """기록 스트림을 봇에 복제 공급, 정확 일치 수 측정 (첫 불일치에서 봇 공급 중단)."""
    mine = init[:5] if seat == "FIRST" else init[5:]
    theirs = init[5:] if seat == "FIRST" else init[:5]
    p = Proc(bot_cmd)
    p.send(f"READY {seat}")
    if p.recv(5.0) != "OK":
        p.close()
        return 0, 0, ("READY-fail", None, None)
    p.send("INIT " + " ".join(mine) + " " + " ".join(theirs))

    total = exact = 0
    first_mm = None
    for side, cell, placed, drawn, _ in moves:
        if side == seat:
            total += 1
            if first_mm is None:
                p.send("TIME 10000 10000")
                ln = p.recv(15.0) or ""
                parts = ln.split()
                pred = (parts[2], parts[1]) if len(parts) == 3 and parts[0] == "PUT" else None
                if pred == (placed, cell):
                    exact += 1
                    p.send(f"GET {drawn}")
                else:
                    first_mm = (total, pred, (placed, cell))
        else:
            if first_mm is None:
                p.send(f"OPP {cell} {placed} {drawn} 0")
    p.send("FINISH")
    p.close()
    return exact, total, first_mm


def _cell_orders():
    cols = "abcdef"
    colmajor = list(CELLS)  # 열 a..f × 행 1..6 × −,+ (압축 id 순)
    rowmajor = [f"{c}{r}{s}" for r in "123456" for c in cols for s in "-+"]
    rowmajor = [c for c in rowmajor if c in set(CELLS)]
    return {"colmajor": colmajor, "rowmajor": rowmajor}


TYPE_ORDER = [f"{c}{p}" for c in "RGBY" for p in "1234"]


def variant_pass(moves, init, seat):
    """동률 해소 가설 격자: 타일순서 × 순회축 × 칸순서 × 비교연산. 각 변형의 전 수 일치율.

    상태는 기록을 따라가므로(예측 독립) 발산 없이 32수 전부 비교 가능.
    """
    cell_orders = _cell_orders()
    variants = {}
    for tile_ord in ("arrival", "typeid"):
        for outer in ("tile", "cell"):
            for corder in ("colmajor", "rowmajor"):
                for ge in (False, True):
                    variants[(tile_ord, outer, corder, ge)] = 0

    hands = {"FIRST": list(init[:5]), "SECOND": list(init[5:])}
    board = {}
    my_idx, opp_idx = (1, 0) if seat == "FIRST" else (0, 1)
    total = 0
    for side, cell, placed, drawn, _ in moves:
        if side == seat:
            total += 1
            base_my = component_sq_sum(board, my_idx)
            base_opp = component_sq_sum(board, opp_idx)
            vals = {}
            for t in set(hands[side]):
                for c in CELLS:
                    if c in board:
                        continue
                    board[c] = t
                    vals[(t, c)] = (component_sq_sum(board, my_idx) - base_my) - (
                        component_sq_sum(board, opp_idx) - base_opp
                    )
                    del board[c]
            arrival = list(dict.fromkeys(hands[side]))  # 도착 순서, 중복 제거
            typeid = [t for t in TYPE_ORDER if t in set(hands[side])]
            for key in variants:
                tile_ord, outer, corder, ge = key
                tiles = arrival if tile_ord == "arrival" else typeid
                cells = [c for c in cell_orders[corder] if c not in board]
                pairs = ((t, c) for t in tiles for c in cells) if outer == "tile" else (
                    (t, c) for c in cells for t in tiles)
                best, pick = None, None
                for t, c in pairs:
                    v = vals[(t, c)]
                    if best is None or v > best or (ge and v == best):
                        best, pick = v, (t, c)
                if pick == (placed, cell):
                    variants[key] += 1
        board[cell] = placed
        hands[side].remove(placed)
        if drawn != "X0":
            hands[side].append(drawn)
    return variants, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--seat", choices=["FIRST", "SECOND"], default="SECOND",
                    help="사이트 봇이 앉은 시트 (기본 SECOND = p1human 로그)")
    ap.add_argument("--bot", action="append",
                    help="섀도 후보 봇 커맨드 (복수 지정 가능)")
    ap.add_argument("--variants", action="store_true", help="동률 해소 가설 격자 검정")
    args = ap.parse_args()
    bots = args.bot or ["build/sample_ai s1", "build/sample_ai c3", "build/sample_ai c2"]

    init, moves, scores = parse_log(args.log)
    print(f"log: {os.path.basename(args.log)}  (seat={args.seat}, 기록 점수 {scores})")

    # 주머니 모델 상시 체크: 각자 16종×2장 (docs/GAME_RULES.md 판정 근거 유지)
    from collections import Counter
    acq = {"FIRST": Counter(init[:5]), "SECOND": Counter(init[5:])}
    for side, _c, _p, drawn, _f in moves:
        if drawn != "X0":
            acq[side][drawn] += 1
    bag_ok = all(max(c.values()) <= 2 and sum(c.values()) <= 32 for c in acq.values())
    print(f"[주머니 모델] 각자 16종x2장: {'일치' if bag_ok else '위반!! 규칙 재검토 필요'} "
          f"(F {sum(acq['FIRST'].values())}장/max{max(acq['FIRST'].values())}, "
          f"S {sum(acq['SECOND'].values())}장/max{max(acq['SECOND'].values())})")

    total, members, ties, misses = policy_class_pass(moves, init, args.seat)
    print(f"[정책 클래스] 1-ply 마진 그리디 argmax 멤버십: {members}/{total}  (동률 국면 {ties}회)")
    for m in misses[:5]:
        print(f"  ! 이탈: {args.seat} {m[0]}번째 수 {m[1]}@{m[2]} (argmax val={m[3]})")

    if args.variants:
        variants, vt = variant_pass(moves, init, args.seat)
        ranked = sorted(variants.items(), key=lambda kv: -kv[1])
        print(f"[타이브레이크 격자] 상위 6 / {len(ranked)}종 (전 {vt}수 기준):")
        for (tile_ord, outer, corder, ge), n in ranked[:6]:
            cmp_s = ">=" if ge else ">"
            print(f"  {n:>2}/{vt}  tile={tile_ord:<7} outer={outer:<4} cells={corder:<8} cmp={cmp_s}")

    for cmd in bots:
        exact, tot, mm = shadow_pass(moves, init, args.seat, cmd)
        line = f"[섀도 일치] {cmd}: {exact}/{tot}"
        if mm:
            line += f"  (첫 불일치 {mm[0]}번째 수: 예측 {mm[1]} vs 기록 {mm[2]})"
        else:
            line += "  → 타이브레이크까지 완전 동일 정책"
        print(line)


if __name__ == "__main__":
    main()
