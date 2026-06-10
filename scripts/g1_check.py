#!/usr/bin/env python3
"""G1 게이트 — 공식 sample-code 와 c2 의 동작 일치(섀도 비교).

공식 바이너리가 실제 플레이어로 한 판을 두는 동안, 동일한 입력 스트림을 c2(섀도)에도
복제 공급하고 매 TIME 마다 두 출력(PUT)을 비교한다. 전 수 일치 → 같은 정책.
(버섯 1,332/1,332 검증과 같은 방법론. 불일치 시 c2 의 순회/타이브레이크를 보정한다.)

사용 (WSL):
  python3 scripts/g1_check.py --official build/official_sample --shadow "build/sample_ai c2" \
      --sparring "build/sample_ai c3" --seeds 4
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connexion_rules import CELL_SET, full_bag  # noqa: E402
from referee import GRACE_S, Proc  # noqa: E402


def shadow_game(official_cmd, shadow_cmd, sparring_cmd, seed, official_first):
    """공식 vs 스파링 한 판 + 섀도 복제. 반환: (mismatch ply or None, 진행 수)."""
    rng = random.Random(seed)
    bags = []
    for _ in range(2):
        bag = full_bag()
        rng.shuffle(bag)
        bags.append(bag)
    hands = [[bags[p].pop() for _ in range(5)] for p in range(2)]

    off_seat = 0 if official_first else 1
    official = Proc(official_cmd)
    shadow = Proc(shadow_cmd)
    sparring = Proc(sparring_cmd)
    seats = {off_seat: official, 1 - off_seat: sparring}

    def to_official(line):
        official.send(line)
        shadow.send(line)

    def cleanup():
        for pr in (official, shadow, sparring):
            pr.send("FINISH")
            pr.close()

    mismatch = None
    try:
        to_official("READY " + ("FIRST" if off_seat == 0 else "SECOND"))
        sparring.send("READY " + ("FIRST" if off_seat == 1 else "SECOND"))
        for pr in (official, shadow, sparring):
            if pr.recv(5.0) != "OK":
                cleanup()
                return ("READY-fail", 0)
        to_official("INIT " + " ".join(hands[off_seat]) + " " + " ".join(hands[1 - off_seat]))
        sparring.send("INIT " + " ".join(hands[1 - off_seat]) + " " + " ".join(hands[off_seat]))

        board = {}
        for ply in range(64):
            p = ply & 1
            if p == off_seat:
                to_official("TIME 10000 10000")
                out_o = official.recv(10 + GRACE_S)
                out_s = shadow.recv(10 + GRACE_S)
                if out_o != out_s:
                    mismatch = (ply, out_o, out_s)
                    break
                ln = out_o
            else:
                sparring.send("TIME 10000 10000")
                ln = sparring.recv(10 + GRACE_S)
            parts = (ln or "").split()
            if len(parts) != 3 or parts[0] != "PUT" or parts[1] not in CELL_SET or parts[1] in board:
                mismatch = (ply, "protocol-error", ln)
                break
            cell, tile = parts[1], parts[2]
            board[cell] = tile
            hands[p].remove(tile)
            drawn = bags[p].pop() if bags[p] else None
            if drawn:
                hands[p].append(drawn)
            if p == off_seat:
                to_official(f"GET {drawn or 'X0'}")
                sparring.send(f"OPP {cell} {tile} {drawn or 'X0'} 10000")
            else:
                sparring.send(f"GET {drawn or 'X0'}")
                to_official(f"OPP {cell} {tile} {drawn or 'X0'} 10000")
        cleanup()
        return (mismatch, 64 if mismatch is None else mismatch[0])
    except Exception as e:
        cleanup()
        return ((f"error: {e}",), 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", required=True, help="공식 sample-code 바이너리")
    ap.add_argument("--shadow", default="build/sample_ai c2")
    ap.add_argument("--sparring", default="build/sample_ai c3")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=7000)
    args = ap.parse_args()

    total = ok = 0
    for s in range(args.seeds):
        for first in (True, False):
            total += 1
            mm, plies = shadow_game(args.official, args.shadow, args.sparring,
                                    args.seed_base + s, first)
            tag = f"seed={args.seed_base + s} {'선공' if first else '후공'}"
            if mm is None:
                ok += 1
                print(f"  {tag}: 일치 (공식 측 수 전부 동일)")
            else:
                print(f"  {tag}: 불일치 @ {mm}")
    print(f"G1: {ok}/{total} 게임 전 수 일치" + ("  → PASS" if ok == total else "  → c2 보정 필요"))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
