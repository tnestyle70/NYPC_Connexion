#!/usr/bin/env python3
"""Connexion referee — 공식 채점 방식("샘플 AI와의 대결")의 로컬 미러.

- 서버 역할: 주머니 셔플(시드), READY/INIT/TIME/GET/OPP/FINISH 프로토콜, 수 검증, 점수.
- 채점: 승 1 / 무 0.5 / 패 0, 선후공 교대. ladder 모드 = c1~c7 x 2판 = 14배틀 "X승/14 (A/B/C)".
- 결정론: 같은 시드 + 결정론 봇 → 같은 수순 (scripts/ladder_check.py G4 로 검증).

사용 (WSL):
  python3 scripts/referee.py pair --a "build/sample_ai c3" --b "build/sample_ai c2" --games 2 --seed-base 1
  python3 scripts/referee.py ladder --target "build/sample_ai c7" --exe build/sample_ai --seed-base 100
"""

import argparse
import json
import os
import queue
import random
import shlex
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connexion_rules import CELL_SET, full_bag, score  # noqa: E402

CLOCK_MS_DEFAULT = 10_000
READY_TIMEOUT_S = 3.0
GRACE_S = 5.0  # 로컬 파이프/스케줄링 여유 (시계 판정은 clocks 로 별도)

LADDER_TIERS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]
TIER_GROUP = {"c1": "A", "c2": "A", "c3": "B", "c4": "B", "c5": "B", "c6": "C", "c7": "C"}


class Proc:
    """라인 기반 봇 프로세스 래퍼 (reader thread + queue, 타임아웃 recv)."""

    def __init__(self, cmd):
        self.cmd = cmd
        self.p = subprocess.Popen(
            shlex.split(cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.q = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            for line in self.p.stdout:
                self.q.put(line.rstrip("\n"))
        except Exception:
            pass
        self.q.put(None)  # EOF

    def send(self, s):
        try:
            self.p.stdin.write(s + "\n")
            self.p.stdin.flush()
        except Exception:
            pass

    def recv(self, timeout_s):
        try:
            return self.q.get(timeout=timeout_s)
        except queue.Empty:
            return "<TIMEOUT>"

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=2)
        except Exception:
            self.p.kill()


def play_game(cmd_first, cmd_second, seed, clock_ms=CLOCK_MS_DEFAULT, strict_time=False):
    """한 판 진행. seat 0 = 선공(문양), seat 1 = 후공(색).

    주머니 규약: random.Random(seed) 로 bag0, bag1 순서대로 shuffle, 드로우 = pop() (리스트 끝).
    """
    rng = random.Random(seed)
    bags = []
    for _ in range(2):
        bag = full_bag()
        rng.shuffle(bag)
        bags.append(bag)
    hands = [[bags[p].pop() for _ in range(5)] for p in range(2)]

    result = {
        "seed": seed,
        "first": cmd_first,
        "second": cmd_second,
        "hands0": [list(hands[0]), list(hands[1])],  # 초기 손패 (visualizer 리플레이용)
        "moves": [],
        "score_first": 0,
        "score_second": 0,
        "winner": None,
        "fault": None,
        "max_move_ms": [0, 0],
    }

    procs = [Proc(cmd_first), Proc(cmd_second)]
    board = {}
    clocks = [clock_ms, clock_ms]

    def finish(winner, fault=None):
        for pr in procs:
            pr.send("FINISH")
        for pr in procs:
            pr.close()
        sf, ss = score(board)
        result["score_first"], result["score_second"] = sf, ss
        result["winner"] = winner
        result["fault"] = fault
        return result

    def fault_out(seat, reason):
        return finish("second" if seat == 0 else "first", {"seat": seat, "reason": reason})

    try:
        for p in (0, 1):
            procs[p].send("READY " + ("FIRST" if p == 0 else "SECOND"))
        for p in (0, 1):
            ln = procs[p].recv(READY_TIMEOUT_S)
            if ln != "OK":
                return fault_out(p, f"READY response: {ln!r}")
        for p in (0, 1):
            procs[p].send("INIT " + " ".join(hands[p]) + " " + " ".join(hands[1 - p]))

        for ply in range(64):
            p = ply & 1
            procs[p].send(f"TIME {max(clocks[p], 0)} {max(clocks[1 - p], 0)}")
            t0 = time.perf_counter()
            ln = procs[p].recv(max(clocks[p], 0) / 1000.0 + GRACE_S)
            dt = int((time.perf_counter() - t0) * 1000)
            clocks[p] -= dt
            result["max_move_ms"][p] = max(result["max_move_ms"][p], dt)
            if ln is None or ln == "<TIMEOUT>":
                return fault_out(p, f"ply {ply}: no PUT (EOF/timeout)")
            if strict_time and clocks[p] < 0:
                return fault_out(p, f"ply {ply}: TLE (clock {clocks[p]}ms)")
            parts = ln.split()
            if len(parts) != 3 or parts[0] != "PUT":
                return fault_out(p, f"ply {ply}: bad output {ln!r}")
            cell, tile = parts[1], parts[2]
            if cell not in CELL_SET or cell in board:
                return fault_out(p, f"ply {ply}: illegal cell {cell}")
            if tile not in hands[p]:
                return fault_out(p, f"ply {ply}: tile {tile} not in hand")
            board[cell] = tile
            hands[p].remove(tile)
            drawn = bags[p].pop() if bags[p] else None
            if drawn:
                hands[p].append(drawn)
            procs[p].send(f"GET {drawn or 'X0'}")
            procs[1 - p].send(f"OPP {cell} {tile} {drawn or 'X0'} {max(clocks[p], 0)}")
            result["moves"].append(
                {"ply": ply, "seat": p, "cell": cell, "tile": tile, "draw": drawn or "X0", "ms": dt}
            )

        sf, ss = score(board)
        winner = "first" if sf > ss else "second" if ss > sf else "draw"
        return finish(winner)
    except Exception as e:  # 하네스 자체 오류는 무효 판정으로 기록
        return finish("error", {"seat": -1, "reason": f"referee error: {e}"})


def points(result, seat):
    """seat(0=first,1=second) 기준 승점."""
    w = result["winner"]
    if w == "draw":
        return 0.5
    if w == "first":
        return 1.0 if seat == 0 else 0.0
    if w == "second":
        return 1.0 if seat == 1 else 0.0
    return 0.0  # error


def log_result(path, result):
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def cmd_pair(args):
    total_a = 0.0
    for i in range(args.games):
        a_first = i % 2 == 0
        cf, cs = (args.a, args.b) if a_first else (args.b, args.a)
        r = play_game(cf, cs, args.seed_base + i, args.clock_ms, args.strict_time)
        seat_a = 0 if a_first else 1
        pa = points(r, seat_a)
        total_a += pa
        log_result(args.log, r)
        fault = f"  fault={r['fault']}" if r["fault"] else ""
        print(
            f"[game {i}] seed={r['seed']} first={'A' if a_first else 'B'} "
            f"score {r['score_first']}:{r['score_second']} winner={r['winner']} "
            f"(A +{pa}){fault}  max_ms={r['max_move_ms']}"
        )
    print(f"A({args.a}) {total_a}승 / {args.games}판  vs  B({args.b})")


def cmd_ladder(args):
    total = 0.0
    group_pts = {"A": 0.0, "B": 0.0, "C": 0.0}
    group_max = {"A": 0, "B": 0, "C": 0}
    seed = args.seed_base
    print(f"target: {args.target}  (seed base {args.seed_base})")
    for tier in LADDER_TIERS:
        tier_cmd = f"{args.exe} {tier}"
        pts = 0.0
        details = []
        for target_first in (True, False):
            cf, cs = (args.target, tier_cmd) if target_first else (tier_cmd, args.target)
            r = play_game(cf, cs, seed, args.clock_ms, args.strict_time)
            seed += 1
            p = points(r, 0 if target_first else 1)
            pts += p
            log_result(args.log, r)
            details.append(
                f"{'선' if target_first else '후'} {r['score_first']}:{r['score_second']}"
                + (f" fault={r['fault']['seat']}" if r["fault"] else "")
            )
        g = TIER_GROUP[tier]
        group_pts[g] += pts
        group_max[g] += 2
        total += pts
        print(f"  vs {tier} [{g}]  +{pts}/2   ({', '.join(details)})")
    print(
        f"결과: {total}승 / 14  "
        f"(A {group_pts['A']}/{group_max['A']} | B {group_pts['B']}/{group_max['B']} | "
        f"C {group_pts['C']}/{group_max['C']})"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    pp = sub.add_parser("pair", help="봇 A vs B, N판 선후공 교대")
    pp.add_argument("--a", required=True)
    pp.add_argument("--b", required=True)
    pp.add_argument("--games", type=int, default=2)
    pp.add_argument("--seed-base", type=int, default=1)
    pp.add_argument("--clock-ms", type=int, default=CLOCK_MS_DEFAULT)
    pp.add_argument("--strict-time", action="store_true")
    pp.add_argument("--log", default="Log/SelfplayOracle/referee_pair.jsonl")
    pp.set_defaults(fn=cmd_pair)

    lp = sub.add_parser("ladder", help="target vs c1~c7 x 선후 2판 = 14배틀")
    lp.add_argument("--target", required=True)
    lp.add_argument("--exe", default="build/sample_ai")
    lp.add_argument("--seed-base", type=int, default=100)
    lp.add_argument("--clock-ms", type=int, default=CLOCK_MS_DEFAULT)
    lp.add_argument("--strict-time", action="store_true")
    lp.add_argument("--log", default="Log/SelfplayOracle/referee_ladder.jsonl")
    lp.set_defaults(fn=cmd_ladder)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
