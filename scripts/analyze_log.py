"""Generic replay + 1-ply-greedy regret analysis for any Connexion website log.

Usage: python scripts/analyze_log.py <path-to-log>

Reuses the verified topology/scoring from analyze_game.py (official finals_1 rules).
For each move computes val = (dSelf - dOpp) of the played action vs the 1-ply
greedy optimum over (hand tile x empty cell); a side whose average regret is ~0
is (consistent with) the official website sample AI.
"""

import sys
from analyze_game import ADJ, SLOTS, comps, score
from recover_rules import parse_log


def main(path):
    init, moves, scores = parse_log(path)
    hands = {"FIRST": list(init[:5]), "SECOND": list(init[5:])}
    board = {}
    rows, regrets = [], []
    x0_onset = None

    for i, (side, cell, placed, drawn, _) in enumerate(moves):
        if drawn == "X0" and x0_onset is None:
            x0_onset = i + 1
        empties = [c for c in SLOTS if c not in board]
        base1, base2 = score(board, 1), score(board, 0)
        my_idx, opp_idx = (1, 0) if side == "FIRST" else (0, 1)
        my_base, opp_base = (base1, base2) if side == "FIRST" else (base2, base1)
        best_val, best_mv, played_val = None, None, None
        for t in set(hands[side]):
            for c in empties:
                board[c] = t
                v_my = score(board, my_idx) - my_base
                v_opp = score(board, opp_idx) - opp_base
                del board[c]
                val = v_my - v_opp
                if best_val is None or val > best_val:
                    best_val, best_mv = val, (t, c, v_my, v_opp)
                if t == placed and c == cell:
                    played_val = (val, v_my, v_opp)

        board[cell] = placed
        n1, n2 = score(board, 1), score(board, 0)
        rows.append((i + 1, side, cell, placed, n1 - base1, n2 - base2, n1, n2))
        regrets.append((best_val - played_val[0], i + 1, side, cell, placed,
                        played_val, best_mv, best_val))
        hands[side].remove(placed)
        if drawn != "X0":
            hands[side].append(drawn)

    print(f"log: {path}")
    print(f"moves: {len(moves)} | X0 onset: move {x0_onset}")
    print(f"replay final: P1(pattern) {rows[-1][6]}  P2(color) {rows[-1][7]}"
          f" | log says {scores} | match: "
          f"{rows[-1][6] == scores.get('FIRST') and rows[-1][7] == scores.get('SECOND')}")

    for side in ("FIRST", "SECOND"):
        rs = [r for r in regrets if r[2] == side]
        zero = sum(1 for r in rs if r[0] == 0)
        avg = sum(r[0] for r in rs) / len(rs)
        print(f"{side:<6}: avg 1-ply regret {avg:5.2f} | greedy-optimal moves {zero}/{len(rs)}")

    gift = {"FIRST": [0, 0], "SECOND": [0, 0]}
    for _, side, _, _, d1, d2, _, _ in rows:
        gift[side][0] += d1
        gift[side][1] += d2
    print("\nscore contribution by mover (pattern=P1 metric, color=P2 metric):")
    print(f"  FIRST  moves: pattern {gift['FIRST'][0]:+4d}, color {gift['FIRST'][1]:+4d}")
    print(f"  SECOND moves: pattern {gift['SECOND'][0]:+4d}, color {gift['SECOND'][1]:+4d}")

    fin = dict(board)
    print("\nP1 pattern components (size>=2):")
    for a, m in sorted(comps(fin, 1), key=lambda x: -len(x[1])):
        if len(m) >= 2:
            who = sum(1 for r in rows if r[2] in m and r[1] == "FIRST")
            print(f"  pattern {a}: size {len(m):>2} (+{len(m)**2:>3}) [by P1: {who}/{len(m)}] {sorted(m)}")
    print("P2 color components (size>=2):")
    for a, m in sorted(comps(fin, 0), key=lambda x: -len(x[1])):
        if len(m) >= 2:
            who = sum(1 for r in rows if r[2] in m and r[1] == "SECOND")
            print(f"  color {a}: size {len(m):>2} (+{len(m)**2:>3}) [by P2: {who}/{len(m)}] {sorted(m)}")

    for side in ("FIRST", "SECOND"):
        print(f"\ntop-8 regret moves for {side} (val = dSelf - dOpp):")
        for reg, mv, sd, cell, placed, pv, bm, bv in sorted(
                (r for r in regrets if r[2] == side), reverse=True)[:8]:
            print(f"  mv{mv:>2} played {placed}@{cell} val={pv[0]:+} (self{pv[1]:+}/opp{pv[2]:+})"
                  f" | best {bm[0]}@{bm[1]} val={bv:+} (self{bm[2]:+}/opp{bm[3]:+}) | regret {reg}")

    # score trajectory every 8 moves
    print("\nscore trajectory (move: P1 P2 diff):")
    for r in rows:
        if r[0] % 8 == 0 or r[0] == len(rows):
            print(f"  mv{r[0]:>2}: {r[6]:>3} {r[7]:>3}  ({r[6]-r[7]:+d})")


if __name__ == "__main__":
    main(sys.argv[1])
