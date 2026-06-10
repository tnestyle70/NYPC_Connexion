"""Full replay analysis of the 2026-06-11 sample-AI game (FIRST=human 196, SECOND=AI 304).

OFFICIAL rules (https://nypc.github.io/2025-codebattle/finals_1):
  - 6x6 grid of (+,-) cell pairs, 8 cells excluded -> 64 slots
  - connectivity (degree <= 3, honeycomb):
      (c,r,-) ~ (c,r,+), (c-1,r,+), (c,r-1,+)
    example from the page: c5- ~ {c5+, b5+, c4+}; f4+ ~ {f4-, f5-}
  - scoring: score(player) = sum over connected components of (size^2),
    FIRST groups by pattern digit, SECOND groups by color letter
"""

from collections import defaultdict
from recover_rules import parse_log, label_key, LOG

ALL_LABELS = [f"{chr(97+cx)}{ry+1}{sg}" for cx in range(6) for ry in range(6) for sg in "+-"]
HOLES = {"a1-", "a4-", "c3+", "c6+", "d1-", "d4-", "f3+", "f6+"}
SLOTS = [c for c in ALL_LABELS if c not in HOLES]


def _neighbors(cell):
    col, row, s = ord(cell[0]) - 97, int(cell[1]), cell[2]
    if s == "-":
        cand = [f"{cell[0]}{row}+",
                f"{chr(96 + col)}{row}+" if col >= 1 else None,
                f"{cell[0]}{row - 1}+" if row >= 2 else None]
    else:
        cand = [f"{cell[0]}{row}-",
                f"{chr(98 + col)}{row}-" if col <= 4 else None,
                f"{cell[0]}{row + 1}-" if row <= 5 else None]
    return [c for c in cand if c and c not in HOLES]


ADJ = {c: _neighbors(c) for c in SLOTS}

# brick-wall layout for rendering: x unit = 2*col + (1 if '+' else 0), row 6 on top
LAYOUT = {c: (2 * (ord(c[0]) - 97) + (1 if c[2] == "+" else 0), 6 - int(c[1])) for c in SLOTS}


def comps(board, idx):
    """Components of same attr; board: cell->tile str; idx 0=color,1=pattern."""
    seen, out = set(), []
    for c, t in board.items():
        if c in seen:
            continue
        a = t[idx]
        stack, comp = [c], [c]
        seen.add(c)
        while stack:
            u = stack.pop()
            for v in ADJ[u]:
                if v in board and v not in seen and board[v][idx] == a:
                    seen.add(v)
                    stack.append(v)
                    comp.append(v)
        out.append((a, comp))
    return out


def score(board, idx):
    return sum(len(m) ** 2 for _, m in comps(board, idx))


def main():
    init, moves, scores = parse_log(LOG)
    hands = {"FIRST": list(init[:5]), "SECOND": list(init[5:])}
    board = {}
    s_first = s_second = len_hist = 0
    rows = []
    regrets = []

    for i, (side, cell, placed, drawn, _) in enumerate(moves):
        empties = [c for c in SLOTS if c not in board]
        # 1-ply greedy alternatives over (tile in hand) x (empty cell)
        base1, base2 = score(board, 1), score(board, 0)
        best_val, best_mv = None, None
        played_val = None
        my_idx, opp_idx = (1, 0) if side == "FIRST" else (0, 1)
        my_base, opp_base = (base1, base2) if side == "FIRST" else (base2, base1)
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
        d1, d2 = n1 - base1, n2 - base2
        rows.append((i + 1, side, cell, placed, d1, d2, n1, n2))
        regret = best_val - played_val[0]
        regrets.append((regret, i + 1, side, cell, placed, played_val, best_mv, best_val))

        hands[side].remove(placed)
        if drawn != "X0":
            hands[side].append(drawn)

    print("mv side  cell tile | dPat(P1) dCol(P2) | P1  P2")
    for r in rows:
        print(f"{r[0]:>2} {r[1]:<6} {r[2]}  {r[3]}  | {r[4]:+4d}    {r[5]:+4d}   | {r[6]:>3} {r[7]:>3}")

    print("\nfinal:", rows[-1][6], rows[-1][7], "| log says", scores)

    # who fed whom
    gift = {"FIRST": [0, 0], "SECOND": [0, 0]}  # [dPat, dCol] summed per mover
    for _, side, _, _, d1, d2, _, _ in rows:
        gift[side][0] += d1
        gift[side][1] += d2
    print("\nscore contribution by mover (start board=0):")
    print(f"  FIRST 's moves: pattern(P1) {gift['FIRST'][0]:+}, color(P2) {gift['FIRST'][1]:+}")
    print(f"  SECOND's moves: pattern(P1) {gift['SECOND'][0]:+}, color(P2) {gift['SECOND'][1]:+}")

    # final component breakdown
    fin = {c: t for c, t in board.items()}
    print("\nP1 pattern components (size>=2):")
    for a, m in sorted(comps(fin, 1), key=lambda x: -len(x[1])):
        if len(m) >= 2:
            who = sum(1 for r in rows if r[2] in m and r[1] == "FIRST")
            print(f"  pattern {a}: size {len(m):>2} (+{len(m)**2:>3}) cells={sorted(m)} [placed by P1: {who}/{len(m)}]")
    print("P2 color components (size>=2):")
    for a, m in sorted(comps(fin, 0), key=lambda x: -len(x[1])):
        if len(m) >= 2:
            who = sum(1 for r in rows if r[2] in m and r[1] == "SECOND")
            print(f"  color {a}: size {len(m):>2} (+{len(m)**2:>3}) cells={sorted(m)} [placed by P2: {who}/{len(m)}]")

    print("\ntop-12 regret moves (1-ply greedy, val = dSelf - dOpp):")
    for reg, mv, side, cell, placed, pv, bm, bv in sorted(regrets, reverse=True)[:12]:
        print(f"  mv{mv:>2} {side:<6} played {placed}@{cell} val={pv[0]:+} (self{pv[1]:+}/opp{pv[2]:+})"
              f" | best {bm[0]}@{bm[1]} val={bv:+} (self{bm[2]:+}/opp{bm[3]:+}) | regret {reg}")

    avg_f = sum(r[0] for r in regrets if r[2] == "FIRST") / 32
    avg_s = sum(r[0] for r in regrets if r[2] == "SECOND") / 32
    print(f"\navg 1-ply regret: FIRST {avg_f:.2f} | SECOND {avg_s:.2f}")

    # adjacency sanity: degree histogram and the page's worked examples
    deg = defaultdict(int)
    for c in SLOTS:
        deg[len(ADJ[c])] += 1
    print("\ndegree histogram:", dict(sorted(deg.items())))
    print("c5- ~", sorted(ADJ["c5-"]), "| f4+ ~", sorted(ADJ["f4+"]))


if __name__ == "__main__":
    main()
